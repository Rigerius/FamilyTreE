from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from data import db_session
from forms.register import RegisterForm
from forms.login import LoginForm
from data.users import User
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import os
from forms.familyForm import NewFamilyForm, AddPersonForm, EditPersonForm
from functions import*
from data.families import Family
from data.history import History
from utils.history_logger import HistoryLogger
from utils.family_tree import FamilyTreeGenerator, TreeVisualizationHelper
import json
from datetime import datetime, date
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key_Family_TreE'
login_manager = LoginManager()
login_manager.init_app(app)


@app.route('/')
def index():
    db_session.global_init("db/database.db")
    db_sess = db_session.create_session()
    return render_template('test_1.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Пароли не совпадают")

        db_sess = db_session.create_session()
        try:
            if db_sess.query(User).filter(User.email == form.email.data).first():
                return render_template('register.html', title='Регистрация',
                                       form=form,
                                       message="Такой пользователь уже есть")

            user = User(
                name=form.name.data,
                email=form.email.data
            )
            user.set_password(form.password.data)
            db_sess.add(user)
            db_sess.commit()
        finally:
            db_sess.close()

        return redirect('/login')

    return render_template('register.html', title='Регистрация', form=form)


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.get(User,user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        try:
            user = db_sess.query(User).filter(User.email == form.email.data).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                return redirect("/")
            return render_template('login.html',
                                   message="Неправильный логин или пароль",
                                   form=form)
        finally:
            db_sess.close()

    return render_template('login.html', title='Авторизация', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route('/create_family', methods=['GET', 'POST'])
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
        return redirect(url_for('family_page', family_id=new_family.id))

    return render_template('create_family.html', form=form)



@app.route('/family/<int:family_id>')
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


@app.route('/family/<int:family_id>/add_person', methods=['GET', 'POST'])
@login_required
def add_person(family_id):
    db_sess = db_session.create_session()

    try:

        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет прав для добавления родственников', 'danger')
            return redirect(url_for('family_page', family_id=family_id))

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        form = AddPersonForm()

        # Динамически обновляем choices для всех полей связей
        person_choices = [(pid, p["full_name"]) for pid, p in persons.items()]
        form.spouses_ids.choices = person_choices
        form.parents_ids.choices = person_choices
        form.children_ids.choices = person_choices

        if form.validate_on_submit():
            # Проверка: если нет ни одной связи, но это не первый человек
            if persons and not (form.spouses_ids.data or form.parents_ids.data or form.children_ids.data):
                flash('Выберите хотя бы один тип связи (супруг, родители или дети)', 'danger')
                return render_template('add_person.html', form=form, family=family, persons=persons)

            # Проверка: родителей не может быть больше 2
            if len(form.parents_ids.data) > 2:
                flash('У человека может быть не более 2 родителей', 'danger')
                return render_template('add_person.html', form=form, family=family, persons=persons)

            # Генерируем ID нового человека
            person_id = str(uuid.uuid4())[:8]

            # Рассчитываем возраст
            birth_date = form.birth_date.data if form.birth_date.data else None
            death_date = form.death_date.data if form.death_date.data else None
            age = calculate_age(birth_date, death_date) if birth_date else None

            # Создаём запись о новом человеке
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

            # Список для сообщения о добавленных связях
            added_relations = []

            # ========== 1. Обработка связей СУПРУГ ==========
            for spouse_id in form.spouses_ids.data:
                if spouse_id in persons:
                    # Добавляем супруга к новому человеку
                    if spouse_id not in new_person["spouses"]:
                        new_person["spouses"].append(spouse_id)

                    # Добавляем нового человека как супруга к существующему
                    if "spouses" not in persons[spouse_id]:
                        persons[spouse_id]["spouses"] = []
                    if person_id not in persons[spouse_id]["spouses"]:
                        persons[spouse_id]["spouses"].append(person_id)

                    added_relations.append(f"супруг(а) {persons[spouse_id]['full_name']}")

            # ========== 2. Обработка связей РОДИТЕЛИ ==========
            # Новый человек - ребёнок для выбранных родителей
            for parent_id in form.parents_ids.data:
                if parent_id in persons:
                    # Добавляем родителя новому человеку
                    if parent_id not in new_person["parents"]:
                        new_person["parents"].append(parent_id)

                    # Добавляем нового человека как ребёнка к родителю
                    if "children" not in persons[parent_id]:
                        persons[parent_id]["children"] = []
                    if person_id not in persons[parent_id]["children"]:
                        persons[parent_id]["children"].append(person_id)

                    added_relations.append(f"ребёнок {persons[parent_id]['full_name']}")

            # ========== 3. Обработка связей ДЕТИ ==========
            # Новый человек - родитель для выбранных детей
            for child_id in form.children_ids.data:
                if child_id in persons:
                    # Добавляем ребёнка новому человеку
                    if child_id not in new_person["children"]:
                        new_person["children"].append(child_id)

                    # Добавляем нового человека как родителя к ребёнку
                    if "parents" not in persons[child_id]:
                        persons[child_id]["parents"] = []
                    if person_id not in persons[child_id]["parents"]:
                        persons[child_id]["parents"].append(person_id)

                    added_relations.append(f"родитель {persons[child_id]['full_name']}")

            # Сохраняем нового человека
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

            # Формируем сообщение об успешном добавлении
            if added_relations:
                flash(f'Родственник "{form.full_name.data}" успешно добавлен! Связи: {", ".join(added_relations)}',
                      'success')
            else:
                if not persons:
                    flash(f'Родственник "{form.full_name.data}" успешно добавлен как основатель семьи!', 'success')
                else:
                    flash(f'Родственник "{form.full_name.data}" успешно добавлен!', 'success')

            return redirect(url_for('family_page', family_id=family_id))

        return render_template('add_person.html', form=form, family=family, persons=persons)

    finally:
        db_sess.close()


@app.route('/family/<int:family_id>/edit_person/<person_id>', methods=['GET', 'POST'])
@login_required
def edit_person(family_id, person_id):
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет прав для редактирования', 'danger')
            return redirect(url_for('family_page', family_id=family_id))

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        person = persons.get(person_id)
        if not person:
            flash('Родственник не найден', 'danger')
            return redirect(url_for('family_page', family_id=family_id))

        form = EditPersonForm()

        person_choices = [(pid, p["full_name"]) for pid, p in persons.items() if pid != person_id]
        form.spouses_ids.choices = person_choices
        form.parents_ids.choices = person_choices
        form.children_ids.choices = person_choices

        if form.validate_on_submit():
            if form.delete.data:
                return redirect(url_for('delete_person', family_id=family_id, person_id=person_id))

            old_name = person.get("full_name", "")
            changed_fields = []

            # Проверяем, что изменилось
            if form.full_name.data != old_name:
                changed_fields.append("ФИО")

            if form.gender.data != person.get("gender"):
                changed_fields.append("пол")

            if form.status.data != person.get("status"):
                changed_fields.append("статус")

            # Сохраняем старые связи
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
            return redirect(url_for('person_detail', family_id=family_id, person_id=person_id))

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


@app.route('/family/<int:family_id>/delete_person/<person_id>')
@login_required
def delete_person(family_id, person_id):
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            flash('Семья не найдена', 'danger')
            return redirect(url_for('my_families'))

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            flash('У вас нет прав для удаления', 'danger')
            return redirect(url_for('family_page', family_id=family_id))

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        person = persons.get(person_id)
        if not person:
            flash('Родственник не найден', 'danger')
            return redirect(url_for('family_page', family_id=family_id))

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

        # Логируем удаление
        HistoryLogger.log_person_deleted(
            family_id=family_id,
            user_id=current_user.id,
            user_name=current_user.name,
            person_id=person_id,
            person_name=person_name)

        flash(f'Родственник "{person_name}" успешно удалён!', 'success')
        return redirect(url_for('family_page', family_id=family_id))

    finally:
        db_sess.close()


@app.route('/family/<int:family_id>/person/<person_id>')
@login_required
def person_detail(family_id, person_id):
    db_sess = db_session.create_session()

    family = db_sess.query(Family).filter(Family.id == family_id).first()

    if not family:
        flash('Семья не найдена', 'danger')
        return redirect(url_for('my_families'))

    members = json.loads(family.members) if family.members else []
    if str(current_user.id) not in members:
        flash('У вас нет доступа', 'danger')
        return redirect(url_for('family_page', family_id=family_id))

    family_data = init_family_data(family)
    persons = family_data.get("persons", {})

    person = persons.get(person_id)
    if not person:
        flash('Родственник не найден', 'danger')
        return redirect(url_for('family_page', family_id=family_id))

    return render_template('person_detail.html',
                           family=family,
                           person=person,
                           persons=persons)


@app.route('/family/<int:family_id>/history')
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


@app.route('/family/<int:family_id>/tree')
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


@app.route('/api/family/<int:family_id>/tree.json')
@login_required
def api_family_tree_json(family_id):
    """API для получения данных дерева в формате JSON"""
    db_sess = db_session.create_session()
    try:
        family = db_sess.query(Family).filter(Family.id == family_id).first()

        if not family:
            return jsonify({"error": "Family not found"}), 404

        members = json.loads(family.members) if family.members else []
        if str(current_user.id) not in members:
            return jsonify({"error": "Access denied"}), 403

        family_data = init_family_data(family)
        persons = family_data.get("persons", {})

        generator = FamilyTreeGenerator(persons, family.family_name)
        viz_data = generator.export_for_visualization()

        return jsonify(viz_data)
    finally:
        db_sess.close()


@app.route('/profile')
@login_required
def profile():
    """Страница профиля пользователя"""
    db_sess = db_session.create_session()
    try:
        # Получаем все семьи пользователя
        created_families = db_sess.query(Family).filter(
            Family.creator == str(current_user.id)
        ).all()

        all_families = db_sess.query(Family).all()
        member_families = []
        for family in all_families:
            members = json.loads(family.members) if family.members else []
            if str(current_user.id) in members and family.creator != str(current_user.id):
                member_families.append(family)

        # Подсчитываем общее количество родственников во всех семьях
        total_persons = 0
        for family in all_families:
            members = json.loads(family.members) if family.members else []
            if str(current_user.id) in members:
                family_data = init_family_data(family)
                persons = family_data.get("persons", {})
                total_persons += len(persons)

        # Получаем последнюю активность пользователя
        recent_activities = db_sess.query(History).filter(
            History.user_id == str(current_user.id)
        ).order_by(History.created_at.desc()).limit(5).all()

        # Подсчитываем общее количество изменений
        total_edits = db_sess.query(History).filter(
            History.user_id == str(current_user.id)
        ).count()

        return render_template('profile.html',
                               created_families=created_families,
                               member_families=member_families,
                               total_persons=total_persons,
                               recent_activities=recent_activities,
                               total_edits=total_edits)
    finally:
        db_sess.close()


@app.route('/my_families')
@login_required
def my_families():
    """Страница со списком семей пользователя"""
    db_sess = db_session.create_session()
    try:
        # Получаем семьи, которые создал пользователь
        created_families = db_sess.query(Family).filter(
            Family.creator == str(current_user.id)
        ).all()

        # Получаем семьи, в которых пользователь состоит как участник
        all_families = db_sess.query(Family).all()
        member_families = []
        for family in all_families:
            members = json.loads(family.members) if family.members else []
            if str(current_user.id) in members and family.creator != str(current_user.id):
                member_families.append(family)

        return render_template('my_families.html',
                               created_families=created_families,
                               member_families=member_families)
    finally:
        db_sess.close()


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7070))
    app.run(host='0.0.0.0', port=port)
