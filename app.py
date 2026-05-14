# app.py
from flask import Flask, render_template, session, url_for, redirect, request
from flask_login import LoginManager, login_required, current_user
from data import db_session
from data.users import User
from data.families import Family
from data.history import History
import json

# Импортируем все Blueprint из папки routes
from routes.auth import auth_bp
from routes.families import families_bp
from routes.persons import persons_bp
from routes.api import api_bp
from routes.search import search_bp
from routes.admin import admin_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key_Family_TreE'

# Сначала инициализируем LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Потом инициализируем БД
db_session.global_init("db/database.db")


@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя по ID (обязательная функция для Flask-Login)"""
    db_sess = db_session.create_session()
    try:
        return db_sess.get(User, int(user_id))
    finally:
        db_sess.close()


app.register_blueprint(auth_bp)
app.register_blueprint(families_bp)
app.register_blueprint(persons_bp)
app.register_blueprint(api_bp)
app.register_blueprint(search_bp)
app.register_blueprint(admin_bp)


def get_top_families(db_sess):
    """Получает топ-3 публичных семей по количеству родственников"""
    all_families = db_sess.query(Family).filter(Family.status == True).all()

    families_data = []
    for family in all_families:
        family_data = json.loads(family.data) if family.data else {}
        persons = family_data.get("persons", {})
        persons_count = len(persons)

        # Считаем количество правок из истории
        edits_count = db_sess.query(History).filter(
            History.family_id == family.id
        ).count()

        # Получаем имя создателя
        creator = db_sess.query(User).filter(User.id == int(family.creator)).first()
        creator_name = creator.name if creator else "Неизвестный"

        families_data.append({
            "family": family,
            "creator_name": creator_name,
            "persons_count": persons_count,
            "edits_count": edits_count
        })

    # Сортируем по количеству человек (по убыванию) и берем топ-3
    top_families = sorted(families_data,
                          key=lambda x: x["persons_count"],
                          reverse=True)[:3]

    return top_families


@app.route('/')
def index():
    """Главная страница сайта с красивым лендингом"""
    db_sess = db_session.create_session()
    try:
        # Получаем топ семей для отображения на главной
        top_families = get_top_families(db_sess)

        return render_template('index.html', top_families=top_families)
    finally:
        db_sess.close()


@app.route('/clear-flash')
@login_required
def clear_flash():
    """Очистить все flash-сообщения"""
    session.pop('_flashes', None)
    return redirect(request.referrer or url_for('index'))


# Обработчики ошибок для красивого отображения
@app.errorhandler(404)
def not_found_error(error):
    return render_template('base.html',
                           error_code=404,
                           error_message="Страница не найдена"), 404


@app.errorhandler(500)
def internal_error(error):
    db_sess = db_session.create_session()
    db_sess.rollback()
    db_sess.close()
    return render_template('base.html',
                           error_code=500,
                           error_message="Внутренняя ошибка сервера"), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7070, debug=True)