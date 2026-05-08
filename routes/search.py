# routes/search.py
from flask import Blueprint, render_template, request, flash, jsonify
from flask_login import login_required, current_user
from data import db_session
from data.users import User
from data.families import Family
import json

search_bp = Blueprint('search', __name__, url_prefix='/search')


@search_bp.route('/')
@login_required
def search():
    """Главная страница поиска"""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'users')  # users, families, persons

    if not query:
        return render_template('search.html', query='', results=[], search_type=search_type)

    db_sess = db_session.create_session()
    try:
        results = []

        if search_type == 'users':
            # Поиск пользователей
            users = db_sess.query(User).filter(
                User.name.ilike(f'%{query}%') | User.email.ilike(f'%{query}%')
            ).all()

            for user in users:
                # Получаем количество публичных семей пользователя
                families_count = db_sess.query(Family).filter(
                    Family.creator == str(user.id),
                    Family.status == True
                ).count()

                results.append({
                    'id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'avatar': user.avatar,
                    'created_date': user.created_date,
                    'families_count': families_count,
                    'type': 'user'
                })

        elif search_type == 'families':
            # Поиск семей (будет реализовано позже)
            families = db_sess.query(Family).filter(
                Family.family_name.ilike(f'%{query}%'),
                Family.status == True  # Только публичные семьи
            ).all()

            for family in families:
                members = json.loads(family.members) if family.members else []
                results.append({
                    'id': family.id,
                    'name': family.family_name,
                    'creator_id': family.creator,
                    'members_count': len(members),
                    'created_date': family.created_date,
                    'type': 'family'
                })

        elif search_type == 'persons':
            # Поиск людей в семьях (будет реализовано позже)
            # Получаем все публичные семьи
            public_families = db_sess.query(Family).filter(Family.status == True).all()

            for family in public_families:
                family_data = json.loads(family.data) if family.data else {}
                persons = family_data.get("persons", {})

                for person_id, person in persons.items():
                    full_name = person.get("full_name", "")
                    if query.lower() in full_name.lower():
                        results.append({
                            'id': person_id,
                            'name': full_name,
                            'family_id': family.id,
                            'family_name': family.family_name,
                            'type': 'person'
                        })

        return render_template('search.html',
                               query=query,
                               results=results,
                               search_type=search_type,
                               result_count=len(results))
    finally:
        db_sess.close()


@search_bp.route('/api', methods=['GET'])
@login_required
def api_search():
    """API для поиска (JSON)"""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'users')
    limit = request.args.get('limit', 10, type=int)

    if not query:
        return jsonify({'success': True, 'results': []})

    db_sess = db_session.create_session()
    try:
        results = []

        if search_type == 'users':
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

        return jsonify({'success': True, 'results': results})
    finally:
        db_sess.close()