from flask import Flask, render_template
from flask_login import LoginManager
from data import db_session
from data.users import User

# Импортируем все Blueprint из папки routes
from routes.auth import auth_bp
from routes.families import families_bp
from routes.persons import persons_bp
from routes.api import api_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key_Family_TreE'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'


@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя по ID (обязательная функция для Flask-Login)"""
    db_sess = db_session.create_session()
    try:
        return db_sess.get(User, int(user_id))
    finally:
        db_sess.close()


db_session.global_init("db/database.db")


@app.route('/')
def index():
    """Главная страница сайта"""
    return render_template('test_1.html')


app.register_blueprint(auth_bp)
app.register_blueprint(families_bp)
app.register_blueprint(persons_bp)
app.register_blueprint(api_bp)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7070, debug=False)