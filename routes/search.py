from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from data import db_session
from data.users import User
from data.families import Family
import json

search_bp = Blueprint('search', __name__)


@search_bp.route('/families/search')
@login_required
def search_families():
    query = request.args.get('q', '').strip()
    results = []

    if query:
        db_sess = db_session.create_session()
        try:
            # Ищем все семьи
            all_families = db_sess.query(Family).all()

            for family in all_families:
                # Проверяем, содержит ли название поисковый запрос (без учёта регистра)
                if query.lower() in family.family_name.lower():
                    # Проверяем, есть ли у пользователя доступ к этой семье
                    members = json.loads(family.members) if family.members else []
                    if str(current_user.id) in members or family.status == True:
                        # Получаем данные о семье
                        family_data = json.loads(family.data) if family.data else {}
                        persons = family_data.get("persons", {})

                        results.append({
                            'id': family.id,
                            'name': family.family_name,
                            'description': f"{'Публичная' if family.status else 'Приватная'} семья • {len(persons)} чел. • Создатель ID: {family.creator}",
                            'type': 'family',
                            'url': f'/families/{family.id}'
                        })
        finally:
            db_sess.close()

    return render_template('search_results.html',
                           query=query,
                           category='families',
                           results=results)


@search_bp.route('/persons/search')
@login_required
def search_persons():
    query = request.args.get('q', '').strip()
    results = []

    if query:
        db_sess = db_session.create_session()
        try:
            # Ищем во всех семьях, где пользователь состоит
            all_families = db_sess.query(Family).all()

            for family in all_families:
                members = json.loads(family.members) if family.members else []
                if str(current_user.id) not in members:
                    continue  # Пропускаем семьи без доступа

                family_data = json.loads(family.data) if family.data else {}
                persons = family_data.get("persons", {})

                for person_id, person in persons.items():
                    full_name = person.get("full_name", "")
                    if query.lower() in full_name.lower():
                        results.append({
                            'id': person_id,
                            'name': full_name,
                            'description': f"Семья: {family.family_name} • {person.get('gender', '')} • {person.get('age', '?')} лет",
                            'type': 'person',
                            'url': f'/persons/{family.id}/person/{person_id}'
                        })
        finally:
            db_sess.close()

    return render_template('search_results.html',
                           query=query,
                           category='persons',
                           results=results)


@search_bp.route('/users/search')
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    results = []

    if query:
        db_sess = db_session.create_session()
        try:
            # Ищем пользователей по имени
            users = db_sess.query(User).filter(
                User.name.ilike(f'%{query}%')  # ilike - поиск без учёта регистра
            ).all()

            for user in users:
                # Не показываем пароли и хеши
                results.append({
                    'id': user.id,
                    'name': user.name,
                    'description': f"Email: {user.email} • На сайте с {user.created_date.strftime('%d.%m.%Y') if user.created_date else 'неизвестно'}",
                    'type': 'user',
                    'url': f'/auth/profile'  # Пока что просто ссылка на свой профиль
                })
        finally:
            db_sess.close()

    return render_template('search_results.html',
                           query=query,
                           category='users',
                           results=results)