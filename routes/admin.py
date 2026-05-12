from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from data import db_session
from data.users import User
from data.families import Family
from data.history import History
from utils.permissions import is_admin
import json

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.before_request
@login_required
def check_admin():
    """Проверка прав администратора перед каждым запросом"""
    if not is_admin():
        flash('Доступ запрещён. Только для администраторов.', 'danger')
        return redirect(url_for('index'))


@admin_bp.route('/')
def index():
    """Главная страница админ-панели"""
    db_sess = db_session.create_session()
    try:
        users_count = db_sess.query(User).count()
        families_count = db_sess.query(Family).count()
        public_families_count = db_sess.query(Family).filter(Family.status == True).count()
        private_families_count = families_count - public_families_count

        # Последние действия
        recent_actions = db_sess.query(History).order_by(History.created_at.desc()).limit(10).all()

        return render_template('admin/index.html',
                               users_count=users_count,
                               families_count=families_count,
                               public_families_count=public_families_count,
                               private_families_count=private_families_count,
                               recent_actions=recent_actions)
    finally:
        db_sess.close()


@admin_bp.route('/users')
def users():
    """Список всех пользователей"""
    db_sess = db_session.create_session()
    try:
        users = db_sess.query(User).order_by(User.created_date.desc()).all()
        return render_template('admin/users.html', users=users)
    finally:
        db_sess.close()


@admin_bp.route('/users/<int:user_id>/toggle_admin', methods=['POST'])
def toggle_admin(user_id):
    """Назначить/снять права администратора"""
    db_sess = db_session.create_session()
    try:
        user = db_sess.query(User).filter(User.id == user_id).first()
        if user and user.id != current_user.id:  # Нельзя менять свои права
            user.is_admin = not user.is_admin
            db_sess.commit()
            flash(f'Права пользователя {user.name} изменены', 'success')
        else:
            flash('Нельзя изменить свои права', 'danger')
        return redirect(url_for('admin.users'))
    finally:
        db_sess.close()


@admin_bp.route('/families')
def families():
    """Список всех семей"""
    db_sess = db_session.create_session()
    try:
        all_families = db_sess.query(Family).order_by(Family.created_date.desc()).all()

        all_users = db_sess.query(User).all()
        user_names_by_id = {str(user.id): user.name for user in all_users}

        families_list = []
        for family in all_families:
            members = json.loads(family.members) if family.members else []
            families_list.append({
                'id': family.id,
                'name': family.family_name,
                'creator_name': user_names_by_id.get(family.creator, family.creator),
                'status': family.status,
                'members_count': len(members),
                'created_date': family.created_date
            })

        return render_template('admin/families.html', families=families_list)
    finally:
        db_sess.close()


@admin_bp.route('/families/<int:family_id>/toggle_status', methods=['POST'])
def toggle_family_status(family_id):
    """Изменить статус семьи (публичная/приватная)"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()
        if family:
            family.status = not family.status
            db_sess.commit()
            status_text = 'публичная' if family.status else 'приватная'
            flash(f'Семья "{family.family_name}" теперь {status_text}', 'success')
        return redirect(url_for('admin.families'))
    finally:
        db_sess.close()