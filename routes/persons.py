from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from data import db_session
from data.families import Family
from forms.familyForm import AddPersonForm, EditPersonForm
from utils.history_logger import HistoryLogger
import json
from datetime import datetime, date
import uuid
from functions import *
from utils.family_tree import *

persons_bp = Blueprint('persons', __name__, url_prefix='/persons')


@persons_bp.route('/<int:family_id>/add_person', methods=['GET', 'POST'])
@login_required
def add_person(family_id):
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет прав для добавления родственников', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        form = AddPersonForm()

        person_choices = [(pid, p["full_name"]) for pid, p in persons.items()]
        form.spouses_ids.choices = person_choices
        form.parents_ids.choices = person_choices
        form.children_ids.choices = person_choices

        if form.validate_on_submit():
            if persons and not (form.spouses_ids.data or form.parents_ids.data or form.children_ids.data):
                flash('Выберите хотя бы один тип связи (супруг, родители или дети)', 'danger')
                return render_template('add_person.html', form=form, family=family, persons=persons)

            if len(form.parents_ids.data) > 2:
                flash('У человека может быть не более 2 родителей', 'danger')
                return render_template('add_person.html', form=form, family=family, persons=persons)

            person_id = str(uuid.uuid4())[:8]

            birth_date = form.birth_date.data if form.birth_date.data else None
            death_date = form.death_date.data if form.death_date.data else None
            age = calculate_age(birth_date, death_date) if birth_date else None

            new_person = {
                "id": person_id,
                "full_name": form.full_name.data,
                "gender": form.gender.data,
                "status": form.status.data,
                "birth_date": birth_date.isoformat() if birth_date else None,
                "death_date": death_date.isoformat() if death_date else None,
                "age": age,
                "birth_place": form.birth_place.data,
                "death_place": form.death_place.data,
                "biography": form.biography.data,
                "spouses": [],
                "parents": [],
                "children": [],
                "created_by": str(current_user.id),
                "created_at": datetime.now().isoformat()
            }

            added_relations = []

            # Супруги
            for spouse_id in form.spouses_ids.data:
                if spouse_id in persons:
                    if spouse_id not in new_person["spouses"]:
                        new_person["spouses"].append(spouse_id)
                    if "spouses" not in persons[spouse_id]:
                        persons[spouse_id]["spouses"] = []
                    if person_id not in persons[spouse_id]["spouses"]:
                        persons[spouse_id]["spouses"].append(person_id)
                    added_relations.append(f"супруг(а) {persons[spouse_id]['full_name']}")

            # Родители
            for parent_id in form.parents_ids.data:
                if parent_id in persons:
                    if parent_id not in new_person["parents"]:
                        new_person["parents"].append(parent_id)
                    if "children" not in persons[parent_id]:
                        persons[parent_id]["children"] = []
                    if person_id not in persons[parent_id]["children"]:
                        persons[parent_id]["children"].append(person_id)
                    added_relations.append(f"ребёнок {persons[parent_id]['full_name']}")

            # Дети
            for child_id in form.children_ids.data:
                if child_id in persons:
                    if child_id not in new_person["children"]:
                        new_person["children"].append(child_id)
                    if "parents" not in persons[child_id]:
                        persons[child_id]["parents"] = []
                    if person_id not in persons[child_id]["parents"]:
                        persons[child_id]["parents"].append(person_id)
                    added_relations.append(f"родитель {persons[child_id]['full_name']}")

            persons[person_id] = new_person
            family_data["persons"] = persons
            save_family_data(family, family_data)
            db_sess.commit()

            HistoryLogger.log_person_added(
                family_id=family_id,
                user_id=current_user.id,
                user_name=current_user.name,
                person_id=person_id,
                person_name=form.full_name.data,
                relations=added_relations if added_relations else None)

            if added_relations:
                flash(f'Родственник "{form.full_name.data}" успешно добавлен! Связи: {", ".join(added_relations)}', 'success')
            else:
                if not persons:
                    flash(f'Родственник "{form.full_name.data}" успешно добавлен как основатель семьи!', 'success')
                else:
                    flash(f'Родственник "{form.full_name.data}" успешно добавлен!', 'success')

            return redirect(url_for('families.family_page', family_id=family_id))

        return render_template('add_person.html', form=form, family=family, persons=persons)

    finally:
        db_sess.close()


@persons_bp.route('/<int:family_id>/edit_person/<person_id>', methods=['GET', 'POST'])
@login_required
def edit_person(family_id, person_id):
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет прав для редактирования', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        person = persons.get(person_id)
        if not person:
            flash('Родственник не найден', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        form = EditPersonForm()

        person_choices = [(pid, p["full_name"]) for pid, p in persons.items() if pid != person_id]
        form.spouses_ids.choices = person_choices
        form.parents_ids.choices = person_choices
        form.children_ids.choices = person_choices

        if form.validate_on_submit():
            if form.delete.data:
                return redirect(url_for('persons.delete_person', family_id=family_id, person_id=person_id))

            old_name = person.get("full_name", "")
            changed_fields = []

            if form.full_name.data != old_name:
                changed_fields.append("ФИО")
            if form.gender.data != person.get("gender"):
                changed_fields.append("пол")
            if form.status.data != person.get("status"):
                changed_fields.append("статус")

            old_spouses = set(person.get("spouses", []))
            old_parents = set(person.get("parents", []))
            old_children = set(person.get("children", []))

            new_spouses = set(form.spouses_ids.data)
            new_parents = set(form.parents_ids.data)
            new_children = set(form.children_ids.data)

            if old_spouses != new_spouses:
                changed_fields.append("супруги")
            if old_parents != new_parents:
                changed_fields.append("родители")
            if old_children != new_children:
                changed_fields.append("дети")

            if len(new_parents) > 2:
                flash('У человека может быть не более 2 родителей', 'danger')
                return render_template('edit_person.html', form=form, family=family, person=person)

            birth_date = form.birth_date.data if form.birth_date.data else None
            death_date = form.death_date.data if form.death_date.data else None
            age = calculate_age(birth_date, death_date) if birth_date else None

            person["full_name"] = form.full_name.data
            person["gender"] = form.gender.data
            person["status"] = form.status.data
            person["birth_date"] = birth_date.isoformat() if birth_date else None
            person["death_date"] = death_date.isoformat() if death_date else None
            person["age"] = age
            person["birth_place"] = form.birth_place.data
            person["death_place"] = form.death_place.data
            person["biography"] = form.biography.data

            # Обновляем связи
            for spouse_id in old_spouses - new_spouses:
                if spouse_id in persons and person_id in persons[spouse_id].get("spouses", []):
                    persons[spouse_id]["spouses"].remove(person_id)

            for spouse_id in new_spouses - old_spouses:
                if spouse_id in persons:
                    if "spouses" not in persons[spouse_id]:
                        persons[spouse_id]["spouses"] = []
                    if person_id not in persons[spouse_id]["spouses"]:
                        persons[spouse_id]["spouses"].append(person_id)
            person["spouses"] = list(new_spouses)

            for parent_id in old_parents - new_parents:
                if parent_id in persons and person_id in persons[parent_id].get("children", []):
                    persons[parent_id]["children"].remove(person_id)

            for parent_id in new_parents - old_parents:
                if parent_id in persons:
                    if "children" not in persons[parent_id]:
                        persons[parent_id]["children"] = []
                    if person_id not in persons[parent_id]["children"]:
                        persons[parent_id]["children"].append(person_id)
            person["parents"] = list(new_parents)

            for child_id in old_children - new_children:
                if child_id in persons and person_id in persons[child_id].get("parents", []):
                    persons[child_id]["parents"].remove(person_id)

            for child_id in new_children - old_children:
                if child_id in persons:
                    if "parents" not in persons[child_id]:
                        persons[child_id]["parents"] = []
                    if person_id not in persons[child_id]["parents"]:
                        persons[child_id]["parents"].append(person_id)
            person["children"] = list(new_children)

            family_data["persons"] = persons
            save_family_data(family, family_data)
            db_sess.commit()

            HistoryLogger.log_person_edited(
                family_id=family_id,
                user_id=current_user.id,
                user_name=current_user.name,
                person_id=person_id,
                old_name=old_name,
                new_name=form.full_name.data)

            flash(f'Данные родственника "{form.full_name.data}" успешно обновлены!', 'success')
            return redirect(url_for('persons.person_detail', family_id=family_id, person_id=person_id))

        # Заполняем форму
        form.full_name.data = person.get("full_name", "")
        form.gender.data = person.get("gender", "male")
        form.status.data = person.get("status", "living")

        if person.get("birth_date"):
            form.birth_date.data = datetime.fromisoformat(person["birth_date"]).date()
        if person.get("death_date"):
            form.death_date.data = datetime.fromisoformat(person["death_date"]).date()

        form.birth_place.data = person.get("birth_place", "")
        form.death_place.data = person.get("death_place", "")
        form.biography.data = person.get("biography", "")

        form.spouses_ids.data = person.get("spouses", [])
        form.parents_ids.data = person.get("parents", [])
        form.children_ids.data = person.get("children", [])

        return render_template('edit_person.html', form=form, family=family, person=person)

    finally:
        db_sess.close()


@persons_bp.route('/<int:family_id>/delete_person/<person_id>')
@login_required
def delete_person(family_id, person_id):
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет прав для удаления', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        person = persons.get(person_id)
        if not person:
            flash('Родственник не найден', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        person_name = person.get("full_name", person_id)

        # Удаляем связи
        for spouse_id in person.get("spouses", []):
            if spouse_id in persons and person_id in persons[spouse_id].get("spouses", []):
                persons[spouse_id]["spouses"].remove(person_id)

        for parent_id in person.get("parents", []):
            if parent_id in persons and person_id in persons[parent_id].get("children", []):
                persons[parent_id]["children"].remove(person_id)

        for child_id in person.get("children", []):
            if child_id in persons and person_id in persons[child_id].get("parents", []):
                persons[child_id]["parents"].remove(person_id)

        for pid, p in persons.items():
            if pid != person_id:
                if person_id in p.get("spouses", []):
                    p["spouses"].remove(person_id)
                if person_id in p.get("parents", []):
                    p["parents"].remove(person_id)
                if person_id in p.get("children", []):
                    p["children"].remove(person_id)

        del persons[person_id]

        family_data["persons"] = persons
        save_family_data(family, family_data)
        db_sess.commit()

        HistoryLogger.log_person_deleted(
            family_id=family_id,
            user_id=current_user.id,
            user_name=current_user.name,
            person_id=person_id,
            person_name=person_name)

        flash(f'Родственник "{person_name}" успешно удалён!', 'success')
        return redirect(url_for('families.family_page', family_id=family_id))

    finally:
        db_sess.close()


@persons_bp.route('/<int:family_id>/person/<person_id>')
@login_required
def person_detail(family_id, person_id):
    db_sess = db_session.create_session()
    try:  # ← ДОБАВЛЕН try
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('families.my_families'))
        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет доступа', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        person = persons.get(person_id)
        if not person:
            flash('Родственник не найден', 'danger')
            return redirect(url_for('families.family_page', family_id=family_id))

        return render_template('person_detail.html',
                               family=family,
                               person=person,
                               persons=persons)
    finally:
        db_sess.close()