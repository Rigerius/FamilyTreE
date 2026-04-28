# routes/api.py
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from data import db_session
from data.families import Family
import json
from utils.family_tree import FamilyTreeGenerator

# Создаём Blueprint для API с префиксом /api
api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/v1/families', methods=['GET'])
@login_required
def get_families():
    """API: получить список семей в формате JSON"""
    db_sess = db_session.create_session()
    try:
        all_families = db_sess.query(Family).all()
        user_families = []

        for family in all_families:
            members = json.loads(family.members) if family.members else []
            if str(current_user.id) in members:
                user_families.append({
                    "id": family.id,
                    "name": family.family_name,
                    "status": family.status,
                    "members_count": len(members)
                })

        return jsonify({"success": True, "families": user_families})
    finally:
        db_sess.close()


@api_bp.route('/v1/families/<int:family_id>/persons', methods=['GET'])
@login_required
def get_persons(family_id):
    """API: получить родственников семьи в формате JSON"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            return jsonify({"success": False, "error": "Семья не найдена"}), 404

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            return jsonify({"success": False, "error": "Нет доступа"}), 403

        family_data = json.loads(family.data) if family.data else {}
        persons = family_data.get("persons", {})

        persons_list = []
        for person_id, person in persons.items():
            persons_list.append({
                "id": person_id,
                "full_name": person.get("full_name"),
                "gender": person.get("gender"),
                "birth_date": person.get("birth_date"),
                "age": person.get("age")
            })

        return jsonify({"success": True, "count": len(persons_list), "persons": persons_list})
    finally:
        db_sess.close()


@api_bp.route('/v1/family/<int:family_id>/tree.json', methods=['GET'])
@login_required
def api_family_tree_json(family_id):
    """
    API: получить данные семейного дерева в формате JSON
    URL: /api/v1/family/1/tree.json
    """
    db_sess = db_session.create_session()
    try:
        # 1. Получаем семью
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            return jsonify({"success": False, "error": "Семья не найдена"}), 404

        # 2. Проверяем доступ
        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            return jsonify({"success": False, "error": "Нет доступа"}), 403

        # 3. Получаем данные о родственниках
        family_data = json.loads(family.data) if family.data else {}
        persons = family_data.get("persons", {})

        # 4. Генерируем структуру дерева
        generator = FamilyTreeGenerator(persons, family.family_name)
        tree_data = generator.generate_tree()

        # 5. Возвращаем JSON
        return jsonify({
            "success": True,
            "family_id": family_id,
            "family_name": family.family_name,
            "tree": tree_data
        })
    finally:
        db_sess.close()