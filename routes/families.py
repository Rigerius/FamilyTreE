from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from data import db_session
from data.families import Family
from data.users import User
from data.history import History
from forms.familyForm import NewFamilyForm, AddPersonForm, EditPersonForm
from utils.history_logger import HistoryLogger
import json
from datetime import datetime, date
import uuid
from functions import init_family_data
from utils.family_tree import *

families_bp = Blueprint('families', __name__, url_prefix='/families')


@families_bp.route('/')
@login_required
def my_families():
    """Страница 'Мои семьи' - доступна по адресу /families/"""
    db_sess = db_session.create_session()
    try:
        current_user_id_str = str(current_user.id)

        # Семьи, где пользователь - создатель
        created_families = db_sess.query(Family).filter(Family.creator == current_user_id_str).all()

        # Семьи, где пользователь - участник
        all_families = db_sess.query(Family).all()
        member_families = []
        for family in all_families:
            members = json.loads(family.members) if family.members else []
            if current_user_id_str in members and family.creator != current_user_id_str:
                member_families.append(family)

        # Получаем имена создателей
        all_users = db_sess.query(User).all()
        user_names_by_id = {str(user.id): user.name for user in all_users}

        for family in created_families:
            family.creator_name = user_names_by_id.get(family.creator, family.creator)
        for family in member_families:
            family.creator_name = user_names_by_id.get(family.creator, family.creator)

        return render_template('my_families.html',
                               created_families=created_families,
                               member_families=member_families)
    finally:
        db_sess.close()


@families_bp.route('/create_family', methods=['GET', 'POST'])
@login_required
def create_family():
    form = NewFamilyForm()

    if form.validate_on_submit():
        db_sess = db_session.create_session()
        try:
            existing_family = db_sess.query(Family).filter(
                Family.family_name == form.family_name.data,
                Family.creator == str(current_user.id)
            ).first()

            if existing_family:
                flash('Семья с таким названием уже существует!', 'danger')
                return render_template('create_family.html', form=form)

            new_family = Family()
            new_family.family_name = form.family_name.data
            new_family.status = form.status.data
            new_family.creator = str(current_user.id)
            new_family.editors = json.dumps([str(current_user.id)])
            new_family.members = json.dumps([str(current_user.id)])
            new_family.persons = json.dumps([])
            new_family.data = json.dumps({
                "persons": {},
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            })

            db_sess.add(new_family)
            db_sess.commit()

            family_id = new_family.id
            HistoryLogger.log_family_created(
                family_id=family_id,
                user_id=current_user.id,
                user_name=current_user.name,
                family_name=form.family_name.data)

        finally:
            db_sess.close()

        flash(f'Семья "{form.family_name.data}" успешно создана!', 'success')
        return redirect(url_for('families.family_page', family_id=new_family.id))

    return render_template('create_family.html', form=form)


@families_bp.route('/<int:family_id>')
@login_required
def family_page(family_id):
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет доступа к этой семье', 'danger')
            return redirect(url_for('families.my_families'))

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        # Получаем имена создателей
        all_users = db_sess.query(User).all()
        user_names_by_id = {str(user.id): user.name for user in all_users}
        creator_name = user_names_by_id.get(family.creator, family.creator)

        members_names = [user_names_by_id.get(member_id, member_id) for member_id in members]
        editors = json.loads(family.editors) if family.editors else []
        editors_names = [user_names_by_id.get(editor_id, editor_id) for editor_id in editors]

        # Определяем права
        current_user_id_str = str(current_user.id)
        is_creator = (family.creator == current_user_id_str)
        is_editor = current_user_id_str in editors
        user_can_edit = is_creator or is_editor

        return render_template('family_page.html',
                               family=family,
                               creator_name=creator_name,
                               members_names=members_names,
                               editors_names=editors_names,
                               persons=persons,
                               user_can_edit=user_can_edit,
                               is_creator=is_creator,
                               is_editor=is_editor,
                               is_public=family.status)
    finally:
        db_sess.close()


@families_bp.route('/<int:family_id>/history')
@login_required
def family_history(family_id):
    """Страница истории изменений семьи"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет доступа к истории этой семьи', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        # Получаем историю изменений
        history_records = db_sess.query(History).filter(
            History.family_id == family_id
        ).order_by(History.created_at.desc()).all()

        return render_template('family_history.html',
                               family=family,
                               history_records=history_records)
    finally:
        db_sess.close()


@families_bp.route('/<int:family_id>/tree')
@login_required
def family_tree_view(family_id):
    """Страница визуализации семейного дерева"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет доступа к этой семье', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        # Генерируем дерево - ИСПРАВЛЕНО: используем tree_data вместо generate_tree()
        generator = FamilyTreeGenerator(persons, family.family_name)
        tree_data = generator.tree_data

        # Для разных форматов
        chartjs_data = TreeVisualizationHelper.format_for_chartjs(tree_data)
        text_tree = TreeVisualizationHelper.generate_family_text(generator)

        return render_template('family_tree.html',
                               family=family,
                               tree_data=json.dumps(tree_data, ensure_ascii=False),
                               chartjs_data=chartjs_data,
                               text_tree=text_tree)
    finally:
        db_sess.close()


@families_bp.route('/<int:family_id>/members')
@login_required
def family_members(family_id):
    """Страница управления участниками"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        if family.creator != str(current_user.id):
            flash('Только создатель может управлять участниками', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        members = json.loads(family.members) if family.members else []
        editors = json.loads(family.editors) if family.editors else []

        # Получаем информацию о всех пользователях
        all_users = db_sess.query(User).all()
        user_names_by_id = {str(user.id): user.name for user in all_users}

        # Формируем список участников с информацией
        members_info = []
        for member_id in members:
            members_info.append({
                'id': member_id,
                'name': user_names_by_id.get(member_id, member_id),
                'is_creator': member_id == family.creator,
                'is_editor': member_id in editors
            })

        # Пользователи, которых можно добавить
        available_users = [user for user in all_users if str(user.id) not in members]

        return render_template('family_members.html',
                               family=family,
                               members_info=members_info,
                               available_users=available_users)
    finally:
        db_sess.close()


@families_bp.route('/<int:family_id>/add_member', methods=['POST'])
@login_required
def add_member(family_id):
    """Добавление участника в семью"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        if family.creator != str(current_user.id):
            flash('Только создатель может добавлять участников', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        user_id = request.form.get('user_id')
        role = request.form.get('role', 'member')

        if not user_id:
            flash('Выберите пользователя', 'danger')
            return redirect(url_for('families.family_members', family_id=family_id))

        members = json.loads(family.members) if family.members else []
        editors = json.loads(family.editors) if family.editors else []

        if user_id not in members:
            members.append(user_id)

        if role == 'editor' and user_id not in editors:
            editors.append(user_id)

        family.members = json.dumps(members)
        family.editors = json.dumps(editors)
        db_sess.commit()

        # Получаем имя добавленного пользователя
        user = db_sess.query(User).filter(User.id == int(user_id)).first()
        user_name = user.name if user else user_id

        HistoryLogger.log_member_added(
            family_id=family_id,
            user_id=current_user.id,
            user_name=current_user.name,
            new_member_name=user_name)

        flash(f'Пользователь {user_name} добавлен в семью!', 'success')
        return redirect(url_for('families.family_members', family_id=family_id))
    finally:
        db_sess.close()


@families_bp.route('/<int:family_id>/remove_member/<user_id>')
@login_required
def remove_member(family_id, user_id):
    """Удаление участника из семьи"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        if family.creator != str(current_user.id):
            flash('Только создатель может удалять участников', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        if user_id == family.creator:
            flash('Нельзя удалить создателя семьи', 'danger')
            return redirect(url_for('families.family_members', family_id=family_id))

        members = json.loads(family.members) if family.members else []
        editors = json.loads(family.editors) if family.editors else []

        if user_id in members:
            members.remove(user_id)
        if user_id in editors:
            editors.remove(user_id)

        family.members = json.dumps(members)
        family.editors = json.dumps(editors)
        db_sess.commit()

        user = db_sess.query(User).filter(User.id == int(user_id)).first()
        user_name = user.name if user else user_id

        HistoryLogger.log_member_removed(
            family_id=family_id,
            user_id=current_user.id,
            user_name=current_user.name,
            removed_member_name=user_name)

        flash(f'Пользователь {user_name} удалён из семьи', 'success')
        return redirect(url_for('families.family_members', family_id=family_id))
    finally:
        db_sess.close()


@families_bp.route('/<int:family_id>/change_role/<user_id>', methods=['POST'])
@login_required
def change_role(family_id, user_id):
    """Изменение роли участника"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        if family.creator != str(current_user.id):
            flash('Только создатель может изменять роли', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        role = request.form.get('role', 'member')
        editors = json.loads(family.editors) if family.editors else []

        if role == 'editor' and user_id not in editors:
            editors.append(user_id)
        elif role == 'member' and user_id in editors:
            editors.remove(user_id)

        family.editors = json.dumps(editors)
        db_sess.commit()

        flash('Роль участника обновлена', 'success')
        return redirect(url_for('families.family_members', family_id=family_id))
    finally:
        db_sess.close()