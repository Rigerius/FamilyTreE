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

    family = db_sess.query(Family).filter(Family.id == family_id).first()

    if not family:
        flash('Семья не найдена', 'danger')
        return redirect(url_for('my_families'))

    members = json.loads(family.members) if family.members else []
    if str(current_user.id) not in members:
        flash('У вас нет доступа к этой семье', 'danger')
        return redirect(url_for('my_families'))

    family_data = init_family_data(family)
    persons = family_data.get("persons", {})

    # Получаем имена создателей
    all_users = db_sess.query(User).all()
    user_names_by_id = {str(user.id): user.name for user in all_users}
    creator_name = user_names_by_id.get(family.creator, family.creator)

    members_names = [user_names_by_id.get(member_id, member_id) for member_id in members]
    editors = json.loads(family.editors) if family.editors else []
    editors_names = [user_names_by_id.get(editor_id, editor_id) for editor_id in editors]

    return render_template('family_page.html',
                           family=family,
                           creator_name=creator_name,
                           members_names=members_names,
                           editors_names=editors_names,
                           persons=persons)


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
@login_required
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

        # Генерируем дерево
        generator = FamilyTreeGenerator(persons, family.family_name)
        tree_data = generator.generate_tree()

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