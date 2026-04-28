from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from forms.login import LoginForm
from forms.register import RegisterForm
from data import db_session
import json
from data.users import User
from data.history import History
from data.families import Family

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        try:
            user = db_sess.query(User).filter(User.email == form.email.data).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                # Если есть параметр next (откуда пришли), возвращаем туда
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('index'))  # url_for('index') - ссылка на главную
            flash("Неправильный логин или пароль", "danger")
        finally:
            db_sess.close()
    return render_template('login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации"""
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            flash("Пароли не совпадают", "danger")
            return render_template('register.html', form=form)

        db_sess = db_session.create_session()
        try:
            if db_sess.query(User).filter(User.email == form.email.data).first():
                flash("Такой пользователь уже есть", "danger")
                return render_template('register.html', form=form)

            user = User(name=form.name.data, email=form.email.data)
            user.set_password(form.password.data)
            db_sess.add(user)
            db_sess.commit()

            flash("Регистрация успешна! Войдите в систему.", "success")
            return redirect(url_for('auth.login'))  # Ссылка на маршрут login из этого же Blueprint
        finally:
            db_sess.close()

    return render_template('register.html', form=form)


@auth_bp.route('/logout')
def logout():
    """Выход из системы"""
    logout_user()
    flash("Вы вышли из системы", "info")
    return redirect(url_for('index'))


@auth_bp.route('/profile')
@login_required
def profile():
    """Страница профиля пользователя"""
    db_sess = db_session.create_session()
    try:
        # Функция для инициализации данных семьи (нужна для подсчёта родственников)
        def init_family_data(family):
            if not family.data or family.data == "" or family.data == "{}":
                return {"persons": {}}
            return json.loads(family.data)

        # Получаем все семьи пользователя
        created_families = db_sess.query(Family).filter(
            Family.creator == str(current_user.id)
        ).all()

        all_families = db_sess.query(Family).all()
        member_families = []
        for family in all_families:
            members = json.loads(family.members) if family.members else []
            if str(current_user.id) in members and family.creator != str(current_user.id):
                member_families.append(family)

        # Подсчитываем общее количество родственников во всех семьях
        total_persons = 0
        for family in all_families:
            members = json.loads(family.members) if family.members else []
            if str(current_user.id) in members:
                family_data = init_family_data(family)
                persons = family_data.get("persons", {})
                total_persons += len(persons)

        # Получаем последнюю активность пользователя
        recent_activities = db_sess.query(History).filter(
            History.user_id == str(current_user.id)
        ).order_by(History.created_at.desc()).limit(5).all()

        # Подсчитываем общее количество изменений
        total_edits = db_sess.query(History).filter(
            History.user_id == str(current_user.id)
        ).count()

        return render_template('profile.html',
                               created_families=created_families,
                               member_families=member_families,
                               total_persons=total_persons,
                               recent_activities=recent_activities,
                               total_edits=total_edits)
    finally:
        db_sess.close()