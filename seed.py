from main import app, db, Coffee, ensure_seed_data

with app.app_context():
    db.create_all()
    ensure_seed_data()
    print('Seed ok:', Coffee.query.count())