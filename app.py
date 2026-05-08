from flask import Flask, render_template, session, url_for, redirect, request
from flask_login import LoginManager, login_required
from data import db_session
from data.users import User

from routes.auth import auth_bp
from routes.families import families_bp
from routes.persons import persons_bp
from routes.api import api_bp
from routes.search import search_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key_Family_TreE'

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


# Только после всего этого регистрируем Blueprint'ы
app.register_blueprint(auth_bp)
app.register_blueprint(families_bp)
app.register_blueprint(persons_bp)
app.register_blueprint(api_bp)
app.register_blueprint(search_bp)


@app.route('/')
def index():
    """Главная страница сайта"""
    top_families = []
    try:
        db_sess = db_session.create_session()
        families = db_sess.query(db_session.Family).all() if hasattr(db_session, 'Family') else []

        if not families:
            from data.families import Family
            from data.users import User
            from data.history import History
            families = db_sess.query(Family).all()

        from functions import init_family_data

        family_stats = []
        for family in families:
            family_data = init_family_data(family)
            persons = family_data.get("persons", {})

            edits_count = db_sess.query(History).filter(
                History.family_id == family.id
            ).count()

            family_stats.append({
                'family': family,
                'persons_count': len(persons),
                'edits_count': edits_count
            })

        family_stats.sort(key=lambda x: x['persons_count'], reverse=True)
        top_5 = family_stats[:5]

        all_users = db_sess.query(User).all()
        user_names_by_id = {str(user.id): user.name for user in all_users}

        for stat in top_5:
            stat['creator_name'] = user_names_by_id.get(stat['family'].creator, 'Неизвестный')

        top_families = top_5
        db_sess.close()
    except Exception as e:
        print(f"Ошибка при загрузке топ-семей: {e}")
        import traceback
        traceback.print_exc()

    return render_template('index.html', top_families=top_families)


@app.route('/clear-flash')
@login_required
def clear_flash():
    """Очистить все flash-сообщения"""
    session.pop('_flashes', None)
    return redirect(request.referrer or url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7070, debug=True)