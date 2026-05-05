from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
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
def family_page(family_id):
    """Страница просмотра семьи - публичный доступ для публичных семей"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('index'))

        # Определяем права доступа
        current_user_id_str = str(current_user.id) if current_user.is_authenticated else None
        is_public = family.status == True

        # Проверяем, является ли пользователь участником семьи
        members = json.loads(family.members) if family.members else []
        is_member = current_user_id_str in members if current_user_id_str else False

        # Проверяем, является ли пользователь редактором
        editors = json.loads(family.editors) if family.editors else []
        is_editor = current_user_id_str in editors if current_user_id_str else False

        # Проверяем, является ли пользователь создателем
        is_creator = family.creator == current_user_id_str if current_user_id_str else False

        # Проверяем доступ к просмотру
        if not is_public and not is_member:
            flash('Доступ запрещён. Эта семья является приватной.', 'danger')
            return redirect(url_for('index'))

        # Права на редактирование (только создатель, редакторы и участники)
        user_can_edit = is_creator or is_editor or is_member

        # Загружаем данные семьи
        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        # Получаем имена создателей
        all_users = db_sess.query(User).all()
        user_names_by_id = {str(user.id): user.name for user in all_users}
        creator_name = user_names_by_id.get(family.creator, family.creator)

        members_names = [user_names_by_id.get(member_id, member_id) for member_id in members]
        editors_names = [user_names_by_id.get(editor_id, editor_id) for editor_id in editors]

        return render_template('family_page.html',
                               family=family,
                               family_data=family_data,
                               persons=persons,
                               creator_name=creator_name,
                               members_names=members_names,
                               editors_names=editors_names,
                               user_can_edit=user_can_edit,
                               is_creator=is_creator,
                               is_editor=is_editor,
                               is_member=is_member,
                               is_public=is_public)
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
            return redirect(url_for('my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет доступа к истории этой семьи', 'danger')
            return redirect(url_for('family_page', family_id=family_id))

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
def family_tree_view(family_id):
    """Страница визуализации семейного дерева"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет доступа к этой семье', 'danger')
            return redirect(url_for('family_page', family_id=family_id))

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        generator = FamilyTreeGenerator(persons, family.family_name)

        tree_data_vis = generator.to_visjs()

        chartjs_data = TreeVisualizationHelper.format_for_chartjs(generator.tree_data)
        text_tree = TreeVisualizationHelper.generate_family_text(generator)

        return render_template('family_tree.html',
                               family=family,
                               tree_data=tree_data_vis,
                               chartjs_data=chartjs_data,
                               text_tree=text_tree)
    finally:
        db_sess.close()


@families_bp.route('/<int:family_id>/members')
@login_required
def family_members(family_id):
    """Страница управления участниками семьи"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        # Проверяем доступ (только создатель может управлять участниками)
        if not family.is_creator(current_user.id):
            flash('Только создатель семьи может управлять участниками', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        members = family.get_members_list()
        editors = family.get_editors_list()

        # Получаем имена пользователей
        all_users = db_sess.query(User).all()
        user_names_by_id = {str(user.id): user.name for user in all_users}

        members_info = []
        for member_id in members:
            members_info.append({
                'id': member_id,
                'name': user_names_by_id.get(member_id, 'Неизвестно'),
                'is_creator': family.is_creator(member_id),
                'is_editor': member_id in editors
            })

        # Пользователи, которых можно добавить (не состоящие в семье)
        existing_members = set(members)
        available_users = []
        for user in all_users:
            if str(user.id) not in existing_members and user.id != current_user.id:
                available_users.append({
                    'id': user.id,
                    'name': user.name,
                    'email': user.email
                })

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

        # Только создатель может добавлять участников
        if not family.is_creator(current_user.id):
            flash('Только создатель семьи может добавлять участников', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        user_id = request.form.get('user_id')
        role = request.form.get('role', 'member')  # 'member' или 'editor'

        if not user_id:
            flash('Не указан пользователь', 'danger')
            return redirect(url_for('families.family_members', family_id=family_id))

        user = db_sess.query(User).filter(User.id == int(user_id)).first()
        if not user:
            flash('Пользователь не найден', 'danger')
            return redirect(url_for('families.family_members', family_id=family_id))

        members = family.get_members_list()
        editors = family.get_editors_list()

        if str(user_id) in members:
            flash(f'Пользователь {user.name} уже состоит в семье', 'warning')
            return redirect(url_for('families.family_members', family_id=family_id))

        # Добавляем участника
        members.append(str(user_id))
        if role == 'editor':
            editors.append(str(user_id))

        family.members = json.dumps(members)
        family.editors = json.dumps(editors)
        db_sess.commit()

        # Логируем добавление
        HistoryLogger.log_member_added(
            family_id=family_id,
            user_id=current_user.id,
            user_name=current_user.name,
            new_member_name=user.name
        )

        flash(f'Пользователь {user.name} добавлен в семью с ролью "{role}"', 'success')
        return redirect(url_for('families.family_members', family_id=family_id))
    finally:
        db_sess.close()


@families_bp.route('/<int:family_id>/remove_member/<int:user_id>')
@login_required
def remove_member(family_id, user_id):
    """Удаление участника из семьи"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        # Только создатель может удалять участников
        if not family.is_creator(current_user.id):
            flash('Только создатель семьи может удалять участников', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        # Нельзя удалить самого себя
        if user_id == current_user.id:
            flash('Вы не можете удалить себя из семьи', 'danger')
            return redirect(url_for('families.family_members', family_id=family_id))

        user = db_sess.query(User).filter(User.id == user_id).first()
        user_name = user.name if user else f'ID {user_id}'

        members = family.get_members_list()
        editors = family.get_editors_list()

        if str(user_id) not in members:
            flash(f'Пользователь {user_name} не состоит в семье', 'warning')
            return redirect(url_for('families.family_members', family_id=family_id))

        members.remove(str(user_id))
        if str(user_id) in editors:
            editors.remove(str(user_id))

        family.members = json.dumps(members)
        family.editors = json.dumps(editors)
        db_sess.commit()

        # Логируем удаление
        HistoryLogger.log_member_removed(
            family_id=family_id,
            user_id=current_user.id,
            user_name=current_user.name,
            removed_member_name=user_name
        )

        flash(f'Пользователь {user_name} удалён из семьи', 'success')
        return redirect(url_for('families.family_members', family_id=family_id))
    finally:
        db_sess.close()


@families_bp.route('/<int:family_id>/change_role/<int:user_id>', methods=['POST'])
@login_required
def change_role(family_id, user_id):
    """Изменение роли участника (member/editor)"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        # Только создатель может менять роли
        if not family.is_creator(current_user.id):
            flash('Только создатель семьи может менять роли участников', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        new_role = request.form.get('role')
        if new_role not in ['member', 'editor']:
            flash('Неверная роль', 'danger')
            return redirect(url_for('families.family_members', family_id=family_id))

        user = db_sess.query(User).filter(User.id == user_id).first()
        if not user:
            flash('Пользователь не найден', 'danger')
            return redirect(url_for('families.family_members', family_id=family_id))

        members = family.get_members_list()
        editors = family.get_editors_list()

        if str(user_id) not in members:
            flash(f'Пользователь {user.name} не состоит в семье', 'warning')
            return redirect(url_for('families.family_members', family_id=family_id))

        if new_role == 'editor':
            if str(user_id) not in editors:
                editors.append(str(user_id))
        else:  # member
            if str(user_id) in editors:
                editors.remove(str(user_id))

        family.editors = json.dumps(editors)
        db_sess.commit()

        flash(f'Роль пользователя {user.name} изменена на "{new_role}"', 'success')
        return redirect(url_for('families.family_members', family_id=family_id))
    finally:
        db_sess.close()