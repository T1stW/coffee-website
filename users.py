import shutil
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CAFE_DB = BASE_DIR / 'cafe.db'
USERS_DB = BASE_DIR / 'users.db'
BACKUP_DB = BASE_DIR / 'cafe.before-user-db-migration.db'


def main():
    if not CAFE_DB.exists():
        print('cafe.db was not found; nothing to migrate.')
        return

    with sqlite3.connect(CAFE_DB) as cafe:
        has_user_table = cafe.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user'"
        ).fetchone()
        if not has_user_table:
            print('No user table in cafe.db; nothing to migrate.')
            return
        rows = cafe.execute(
            'SELECT id, username, password_hash FROM user ORDER BY id'
        ).fetchall()

    if not BACKUP_DB.exists():
        shutil.copy2(CAFE_DB, BACKUP_DB)

    users = sqlite3.connect(USERS_DB)
    try:
        users.execute(
            'CREATE TABLE IF NOT EXISTS user ('
            'id INTEGER NOT NULL PRIMARY KEY, '
            'username VARCHAR(80) NOT NULL UNIQUE, '
            'password_hash VARCHAR(255) NOT NULL)'
        )
        for user_id, username, password_hash in rows:
            by_id = users.execute(
                'SELECT id, username, password_hash FROM user WHERE id = ?',
                (user_id,),
            ).fetchone()
            by_name = users.execute(
                'SELECT id, username, password_hash FROM user WHERE username = ?',
                (username,),
            ).fetchone()
            existing = by_id or by_name
            expected = (user_id, username, password_hash)
            if existing and existing != expected:
                raise RuntimeError(
                    f'Account conflict for {username!r}; original cafe.db was left untouched.'
                )
            if not existing:
                users.execute(
                    'INSERT INTO user (id, username, password_hash) VALUES (?, ?, ?)',
                    expected,
                )
        users.commit()
        copied_count = users.execute('SELECT COUNT(*) FROM user').fetchone()[0]
        if copied_count < len(rows):
            raise RuntimeError('Not all accounts were copied; original cafe.db was left untouched.')
    except Exception:
        users.rollback()
        raise
    finally:
        users.close()

    with sqlite3.connect(CAFE_DB) as cafe:
        cafe.execute('PRAGMA foreign_keys = OFF')
        cafe.execute('DROP TABLE user')

    print(f'Migrated {len(rows)} account(s) to users.db.')
    print(f'Backup kept at: {BACKUP_DB.name}')
    print('After confirming login works, delete the backup securely if you no longer need it.')


if __name__ == '__main__':
    main()
