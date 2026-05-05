from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from forms.login import LoginForm
from forms.register import RegisterForm
from data import db_session
import json
from data.users import User
from data.history import History
from data.families import Family
import os
from werkzeug.utils import secure_filename
import secrets

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Расширенный список разрешенных расширений
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    """Проверка расширения файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_avatar(form_picture):
    """Сохраняет аватар пользователя"""
    try:
        # Проверяем расширение файла
        if not allowed_file(form_picture.filename):
            raise ValueError('Недопустимый формат файла. Разрешены: PNG, JPG, JPEG, GIF, WEBP')

        # Генерируем уникальное имя файла
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(secure_filename(form_picture.filename))
        avatar_fn = random_hex + f_ext

        # Путь для сохранения
        avatar_path = os.path.join(current_app.root_path, 'static/avatars', avatar_fn)

        # Создаем папку, если её нет
        os.makedirs(os.path.dirname(avatar_path), exist_ok=True)

        # Сохраняем файл напрямую, без обработки Pillow
        form_picture.save(avatar_path)

        return avatar_fn
    except Exception as e:
        print(f"Ошибка при сохранении аватарки: {e}")
        raise


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
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('index'))
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

            # Обработка аватарки
            if form.avatar.data:
                try:
                    avatar_file = form.avatar.data
                    if avatar_file.filename:  # Проверяем, что файл выбран
                        avatar_fn = save_avatar(avatar_file)
                        user.avatar = f'/static/avatars/{avatar_fn}'
                except Exception as e:
                    flash(f'Ошибка при загрузке аватарки: {str(e)}', 'warning')

            db_sess.add(user)
            db_sess.commit()

            flash("Регистрация успешна! Войдите в систему.", "success")
            return redirect(url_for('auth.login'))
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
    """Страница профиля текущего пользователя"""
    # Перенаправляем на страницу просмотра своего профиля
    return redirect(url_for('auth.view_profile', user_id=current_user.id))


@auth_bp.route('/profile/<int:user_id>')
@login_required
def view_profile(user_id):
    """Просмотр профиля пользователя (своего или чужого)"""
    db_sess = db_session.create_session()
    try:
        # Получаем пользователя
        user = db_sess.query(User).filter(User.id == user_id).first()

        if not user:
            flash('Пользователь не найден', 'danger')
            return redirect(url_for('index'))

        # Определяем, является ли этот профиль профилем текущего пользователя
        is_owner = (user.id == current_user.id)

        # Функция для инициализации данных семьи
        def init_family_data(family):
            if not family.data or family.data == "" or family.data == "{}":
                return {"persons": {}}
            return json.loads(family.data)

        # Получаем все семьи пользователя
        if is_owner:
            # Для владельца - все семьи
            created_families = db_sess.query(Family).filter(
                Family.creator == str(user.id)
            ).all()

            all_families = db_sess.query(Family).all()
            member_families = []
            for family in all_families:
                members = json.loads(family.members) if family.members else []
                if str(user.id) in members and family.creator != str(user.id):
                    member_families.append(family)

            # Подсчитываем общее количество родственников
            total_persons = 0
            for family in all_families:
                members = json.loads(family.members) if family.members else []
                if str(user.id) in members:
                    family_data = init_family_data(family)
                    persons = family_data.get("persons", {})
                    total_persons += len(persons)

            # Получаем последнюю активность (только для владельца)
            recent_activities = db_sess.query(History).filter(
                History.user_id == str(user.id)
            ).order_by(History.created_at.desc()).limit(10).all()

            # Подсчитываем общее количество изменений
            total_edits = db_sess.query(History).filter(
                History.user_id == str(user.id)
            ).count()

            # Для владельца показываем все публичные истории
            public_activities = []

        else:
            # Для чужих профилей показываем только публичные семьи
            created_families = db_sess.query(Family).filter(
                Family.creator == str(user.id),
                Family.status == True
            ).all()

            member_families = []
            all_public_families = db_sess.query(Family).filter(Family.status == True).all()
            for family in all_public_families:
                members = json.loads(family.members) if family.members else []
                if str(user.id) in members and family.creator != str(user.id):
                    member_families.append(family)

            # Собираем ID всех публичных семей пользователя
            public_family_ids = [f.id for f in created_families + member_families]

            # Получаем историю изменений только для публичных семей
            public_activities = db_sess.query(History).filter(
                History.user_id == str(user.id),
                History.family_id.in_(public_family_ids) if public_family_ids else False
            ).order_by(History.created_at.desc()).limit(10).all()

            # Для чужих профилей считаем только публичные семьи
            total_persons = 0
            for family in created_families + member_families:
                family_data = init_family_data(family)
                persons = family_data.get("persons", {})
                total_persons += len(persons)

            recent_activities = []
            total_edits = db_sess.query(History).filter(
                History.user_id == str(user.id),
                History.family_id.in_(public_family_ids) if public_family_ids else False
            ).count()

        # Получаем информацию о семьях для отображения (включаем creator_name)
        all_users = db_sess.query(User).all()
        user_names_by_id = {str(u.id): u.name for u in all_users}

        for family in created_families:
            family.creator_name = user_names_by_id.get(family.creator, family.creator)
        for family in member_families:
            family.creator_name = user_names_by_id.get(family.creator, family.creator)

        return render_template('profile.html',
                               profile_user=user,
                               is_owner=is_owner,
                               created_families=created_families,
                               member_families=member_families,
                               total_persons=total_persons,
                               recent_activities=recent_activities,
                               public_activities=public_activities,
                               total_edits=total_edits)
    finally:
        db_sess.close()


def allowed_file(filename):
    """Проверка разрешённых расширений файлов"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_avatar(form_picture):
    """Сохраняет аватар пользователя"""
    try:
        # Проверяем расширение файла
        if not allowed_file(form_picture.filename):
            raise ValueError('Недопустимый формат файла. Разрешены: PNG, JPG, JPEG, GIF, WEBP')

        # Генерируем уникальное имя файла
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(secure_filename(form_picture.filename))
        avatar_fn = random_hex + f_ext

        # Путь для сохранения
        avatar_path = os.path.join(current_app.root_path, 'static/avatars', avatar_fn)

        # Создаем папку, если её нет
        os.makedirs(os.path.dirname(avatar_path), exist_ok=True)

        # Сохраняем файл напрямую, без обработки Pillow
        form_picture.save(avatar_path)

        return avatar_fn
    except Exception as e:
        print(f"Ошибка при сохранении аватарки: {e}")
        raise


@auth_bp.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Загрузка аватарки для пользователя"""
    try:
        if 'avatar' not in request.files:
            flash('Файл не выбран', 'danger')
            return redirect(url_for('auth.view_profile', user_id=current_user.id))

        file = request.files['avatar']

        if file.filename == '':
            flash('Файл не выбран', 'danger')
            return redirect(url_for('auth.view_profile', user_id=current_user.id))

        # Проверяем размер файла
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)

        if file_size > 5 * 1024 * 1024:
            flash('Файл слишком большой. Максимальный размер: 5 МБ', 'danger')
            return redirect(url_for('auth.view_profile', user_id=current_user.id))

        if not allowed_file(file.filename):
            flash('Недопустимый формат файла. Разрешены: PNG, JPG, JPEG, GIF, WEBP', 'danger')
            return redirect(url_for('auth.view_profile', user_id=current_user.id))

        # Сохраняем аватарку
        avatar_fn = save_avatar(file)

        db_sess = db_session.create_session()
        try:
            user = db_sess.query(User).get(current_user.id)

            if user.avatar:
                old_avatar_path = os.path.join(current_app.root_path, 'static', user.avatar.lstrip('/'))
                if os.path.exists(old_avatar_path):
                    try:
                        os.remove(old_avatar_path)
                    except Exception as e:
                        print(f"Не удалось удалить старый аватар: {e}")

            user.avatar = f'/static/avatars/{avatar_fn}'
            db_sess.commit()

            flash('Аватар успешно обновлен!', 'success')
        except Exception as e:
            db_sess.rollback()
            flash(f'Ошибка при сохранении в базу данных: {str(e)}', 'danger')
        finally:
            db_sess.close()

    except Exception as e:
        flash(f'Ошибка при загрузке аватарки: {str(e)}', 'danger')

    return redirect(url_for('auth.view_profile', user_id=current_user.id))