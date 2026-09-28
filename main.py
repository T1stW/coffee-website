import os
import json
try:
    from importlib import import_module
    from werkzeug.security import generate_password_hash, check_password_hash
    Flask = import_module('flask').Flask
    render_template = import_module('flask').render_template
    request = import_module('flask').request
    redirect = import_module('flask').redirect
    url_for = import_module('flask').url_for
    flash = import_module('flask').flash
    SQLAlchemy = import_module('flask_sqlalchemy').SQLAlchemy
    
    # Импортируем Flask-Login для работы с сессиями
    login_module = import_module('flask_login')
    LoginManager = login_module.LoginManager
    UserMixin = login_module.UserMixin
    login_user = login_module.login_user
    logout_user = login_module.logout_user
    login_required = login_module.login_required
    current_user = login_module.current_user
except ModuleNotFoundError as error:
    raise RuntimeError(
        'Установите зависимости: python -m pip install Flask Flask-SQLAlchemy Flask-Login'
    ) from error

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cafe.db')
USERS_DB_PATH = os.path.join(BASE_DIR, 'users.db')

app = Flask(__name__)
# В продакшене секретный ключ должен береться из os.environ.get('SECRET_KEY')
app.secret_key = os.environ.get('SECRET_KEY', 'super-mega-puper-secret-kluch-bratan')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_BINDS'] = {
    'users': f'sqlite:///{USERS_DB_PATH}',
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Перенаправление, если пользователь не авторизован
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'


# Модель Coffee
class Coffee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(300))
    category = db.Column(db.String(50))  # "coffee" или "dessert"


# Модель User с поддержкой UserMixin для Flask-Login
class CustomerOrder(db.Model):
    __tablename__ = 'customer_orders'
    id = db.Column(db.Integer, primary_key=True)
    # User лежит в отдельном SQLite-файле, поэтому межбазового FK здесь нет.
    user_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('customer_orders.id'), nullable=False)
    coffee_id = db.Column(db.Integer, db.ForeignKey('coffee.id'), nullable=False)
    coffee_name = db.Column(db.String(100), nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)


class User(UserMixin, db.Model):
    __bind_key__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    """Функция загрузки пользователя из сессии при каждом запросе."""
    return User.query.get(int(user_id))


def ensure_seed_data():
    if Coffee.query.first() is not None:
        return

    default_items = [
        Coffee(name='Капучино', price=200, category='coffee'),
        Coffee(name='Латте', price=220, category='coffee'),
        Coffee(name='Чизкейк', price=250, category='dessert'),
    ]
    db.session.add_all(default_items)
    db.session.commit()


# --- Маршруты приложения ---

@app.route('/')
def home():
    items = Coffee.query.all()
    return render_template('index.html', items=items)


@app.route('/coffee/<int:coffee_id>')
def coffee_detail(coffee_id):
    item = Coffee.query.get_or_404(coffee_id)
    return render_template('coffee.html', item=item)


@app.route('/checkout', methods=['POST'])
def checkout():
    try:
        cart_data = json.loads(request.form.get('cart_data', ''))
    except (TypeError, ValueError):
        flash('Корзина пуста или данные заказа некорректны.')
        return redirect(url_for('home'))

    if not isinstance(cart_data, list) or not cart_data:
        flash('Добавьте товары в корзину перед оформлением заказа.')
        return redirect(url_for('home'))

    quantities = {}
    try:
        for entry in cart_data:
            coffee_id = int(entry['id'])
            quantity = int(entry['quantity'])
            if coffee_id < 1 or quantity < 1 or quantity > 99:
                raise ValueError
            quantities[coffee_id] = quantities.get(coffee_id, 0) + quantity
            if quantities[coffee_id] > 99:
                raise ValueError
    except (KeyError, TypeError, ValueError):
        flash('Данные заказа некорректны. Обновите страницу и попробуйте снова.')
        return redirect(url_for('home'))

    products = Coffee.query.filter(Coffee.id.in_(quantities)).all()
    if len(products) != len(quantities):
        flash('Один из товаров больше недоступен. Обновите страницу.')
        return redirect(url_for('home'))

    order = CustomerOrder(user_id=current_user.id if current_user.is_authenticated else None)
    for product in products:
        order.items.append(OrderItem(
            coffee_id=product.id,
            coffee_name=product.name,
            unit_price=product.price,
            quantity=quantities[product.id],
        ))

    db.session.add(order)
    db.session.commit()
    return redirect(url_for('order_success', order_id=order.id))


@app.route('/order/<int:order_id>')
def order_success(order_id):
    order = CustomerOrder.query.get_or_404(order_id)
    return render_template('order_success.html', order=order)


# --- Авторизация и Регистрация ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        # Не удаляем пробелы: они могут быть частью пароля.
        password = request.form.get('password', '')

        if not username or not password:
            flash('Заполните все поля!')
            return render_template('register.html')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Пользователь с таким именем уже существует!')
            return render_template('register.html')

        new_user = User(username=username)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()

        # Автоматический вход после успешной регистрации
        login_user(new_user)
        flash('Регистрация прошла успешно!')
        return redirect(url_for('home'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        # Пароль должен проверяться ровно в том виде, в котором его ввели.
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            # Вход пользователя с сохранением состояния в сессии куки
            login_user(user, remember=True)
            return redirect(url_for('home'))
        else:
            flash('Неверное имя пользователя или пароль.')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    with app.app_context():
        db.create_all()
        ensure_seed_data()
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
