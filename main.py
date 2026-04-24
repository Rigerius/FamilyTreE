from flask import Flask, render_template, request, redirect, url_for, flash, session
from data import db_session
from forms.register import RegisterForm
from forms.login import LoginForm
from data.users import User
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import os
from forms.familyForm import NewFamilyForm, AddPersonForm
from data.families import Family
from functions import*
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
def reqister():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Пароли не совпадают")
        db_sess = db_session.create_session()
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
        user = db_sess.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("/")
        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form)
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
                "updated_at": datetime.now().isoformat(),
                "version": "2.0"
            }
        })

        db_sess.add(new_family)
        db_sess.commit()

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


@app.route('/my_families')
@login_required
def my_families():
    """Страница со всеми семьями пользователя"""
    db_sess = db_session.create_session()

    # Семьи, где пользователь создатель
    created_families = db_sess.query(Family).filter(Family.creator == current_user.id).all()

    # Семьи, где пользователь участник (но не создатель)
    all_families = db_sess.query(Family).all()
    member_families = []
    for family in all_families:
        members = json.loads(family.members) if family.members else []
        if current_user.id in members and family.creator != current_user.id:
            member_families.append(family)

    return render_template('my_families.html',
                           created_families=created_families,
                           member_families=member_families)



if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7070))
    app.run(host='0.0.0.0', port=port)