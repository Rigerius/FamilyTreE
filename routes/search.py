# routes/search.py
from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from data import db_session
from data.users import User
from data.families import Family
import json

search_bp = Blueprint('search', __name__, url_prefix='/search')


@search_bp.route('/')
def search():
    """Главная страница поиска (всегда ищет везде)"""
    query = request.args.get('q', '').strip()

    if not query:
        return render_template('search.html', query='', results={'users': [], 'families': [], 'persons': []},
                               total_count=0)

    db_sess = db_session.create_session()
    try:
        results = {
            'users': [],
            'families': [],
            'persons': []
        }

        # Получаем всех пользователей для сопоставления имён
        all_users = db_sess.query(User).all()
        user_names_by_id = {str(user.id): user.name for user in all_users}

        # 1. Поиск ПОЛЬЗОВАТЕЛЕЙ
        users = db_sess.query(User).filter(
            User.name.ilike(f'%{query}%') | User.email.ilike(f'%{query}%')
        ).all()

        for user in users:
            # Получаем количество публичных семей пользователя
            families_count = db_sess.query(Family).filter(
                Family.creator == str(user.id),
                Family.status == True
            ).count()

            results['users'].append({
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'avatar': user.avatar,
                'created_date': user.created_date,
                'families_count': families_count,
                'type': 'user'
            })

        # 2. Поиск СЕМЕЙ (ТОЛЬКО ПУБЛИЧНЫЕ)
        families = db_sess.query(Family).filter(
            Family.family_name.ilike(f'%{query}%'),
            Family.status == True
        ).all()

        for family in families:
            members = json.loads(family.members) if family.members else []
            creator_name = user_names_by_id.get(family.creator, family.creator)

            family_data = json.loads(family.data) if family.data else {}
            persons = family_data.get("persons", {})

            results['families'].append({
                'id': family.id,
                'name': family.family_name,
                'creator_id': family.creator,
                'creator_name': creator_name,
                'members_count': len(members),
                'persons_count': len(persons),
                'created_date': family.created_date,
                'type': 'family'
            })

        # 3. Поиск ЛЮДЕЙ (в публичных семьях)
        public_families = db_sess.query(Family).filter(Family.status == True).all()

        for family in public_families:
            family_data = json.loads(family.data) if family.data else {}
            persons = family_data.get("persons", {})

            for person_id, person in persons.items():
                full_name = person.get("full_name", "")
                if query.lower() in full_name.lower():
                    parents = []
                    for parent_id in person.get("parents", []):
                        parent = persons.get(parent_id, {})
                        if parent:
                            parents.append(parent.get("full_name", parent_id))

                    results['persons'].append({
                        'id': person_id,
                        'name': full_name,
                        'family_id': family.id,
                        'family_name': family.family_name,
                        'gender': person.get("gender", "male"),
                        'status': person.get("status", "living"),
                        'birth_date': person.get("birth_date"),
                        'age': person.get("age"),
                        'parents': parents,
                        'type': 'person'
                    })

        total_count = len(results['users']) + len(results['families']) + len(results['persons'])

        return render_template('search.html',
                               query=query,
                               results=results,
                               total_count=total_count,
                               user_count=len(results['users']),
                               family_count=len(results['families']),
                               person_count=len(results['persons']))
    finally:
        db_sess.close()


@search_bp.route('/api', methods=['GET'])
def api_search():
    """API для поиска (JSON)"""
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)

    if not query:
        return jsonify({'success': True, 'results': []})

    db_sess = db_session.create_session()
    try:
        results = []

        # Поиск пользователей
        users = db_sess.query(User).filter(
            User.name.ilike(f'%{query}%') | User.email.ilike(f'%{query}%')
        ).limit(limit).all()

        for user in users:
            results.append({
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'avatar': user.avatar,
                'type': 'user'
            })

        # Поиск семей (если не набрали лимит)
        if len(results) < limit:
            families = db_sess.query(Family).filter(
                Family.family_name.ilike(f'%{query}%'),
                Family.status == True
            ).limit(limit - len(results)).all()

            for family in families:
                results.append({
                    'id': family.id,
                    'name': family.family_name,
                    'type': 'family'
                })

        # Поиск родственников (если не набрали лимит)
        if len(results) < limit:
            public_families = db_sess.query(Family).filter(Family.status == True).all()
            for family in public_families:
                if len(results) >= limit:
                    break
                family_data = json.loads(family.data) if family.data else {}
                persons = family_data.get("persons", {})
                for person_id, person in persons.items():
                    if len(results) >= limit:
                        break
                    full_name = person.get("full_name", "")
                    if query.lower() in full_name.lower():
                        results.append({
                            'id': person_id,
                            'name': full_name,
                            'family_id': family.id,
                            'family_name': family.family_name,
                            'type': 'person'
                        })

        return jsonify({'success': True, 'results': results})
    finally:
        db_sess.close()


@search_bp.route('/family/<int:family_id>')
def view_family_from_search(family_id):
    """Переход к семье из результатов поиска"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()
        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('search.search'))

        if not family.status:
            members = json.loads(family.members) if family.members else []
            if str(current_user.id) not in members:
                flash('Доступ к этой семье ограничен', 'danger')
                return redirect(url_for('search.search'))

        return redirect(url_for('families.family_page', family_id=family_id))
    finally:
        db_sess.close()


@search_bp.route('/person/<int:family_id>/<person_id>')
def view_person_from_search(family_id, person_id):
    """Переход к родственнику из результатов поиска"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()
        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('search.search'))

        if not family.status:
            members = json.loads(family.members) if family.members else []
            if str(current_user.id) not in members:
                flash('Доступ к этой семье ограничен', 'danger')
                return redirect(url_for('search.search'))

        return redirect(url_for('persons.person_detail', family_id=family_id, person_id=person_id))
    finally:
        db_sess.close()