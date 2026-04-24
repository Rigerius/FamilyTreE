from flask_wtf import FlaskForm
from wtforms import SubmitField, BooleanField, StringField, TextAreaField, SelectField, DateField, SelectMultipleField
from wtforms.validators import DataRequired, Length, Optional


class NewFamilyForm(FlaskForm):
    family_name = StringField(
        'Название семьи',
        validators=[
            DataRequired(message='Укажите название семьи'),
            Length(min=2, max=50, message='Название должно быть от 2 до 50 символов')
        ],
        render_kw={"placeholder": "Например: Ивановы"}
    )
    status = BooleanField('Публичная семья')
    submit = SubmitField('Создать')


class AddPersonForm(FlaskForm):
    """Форма для добавления родственника с множественными связями разных типов"""
    full_name = StringField(
        'ФИО',
        validators=[
            DataRequired(message='Введите ФИО'),
            Length(min=2, max=100, message='ФИО должно быть от 2 до 100 символов')
        ],
        render_kw={"placeholder": "Иванов Иван Иванович"}
    )

    gender = SelectField(
        'Пол',
        choices=[
            ('male', 'Мужской'),
            ('female', 'Женский')
        ],
        validators=[DataRequired(message='Выберите пол')]
    )

    status = SelectField(
        'Статус',
        choices=[
            ('living', 'Живой'),
            ('deceased', 'Умерший')
        ],
        validators=[DataRequired(message='Выберите статус')]
    )

    birth_date = DateField(
        'Дата рождения',
        validators=[Optional()],
        format='%Y-%m-%d',
        render_kw={"placeholder": "ГГГГ-ММ-ДД"}
    )

    death_date = DateField(
        'Дата смерти',
        validators=[Optional()],
        format='%Y-%m-%d',
        render_kw={"placeholder": "ГГГГ-ММ-ДД"}
    )

    birth_place = StringField(
        'Место рождения',
        validators=[Optional(), Length(max=200)],
        render_kw={"placeholder": "Город, страна"}
    )

    death_place = StringField(
        'Место смерти',
        validators=[Optional(), Length(max=200)],
        render_kw={"placeholder": "Город, страна"}
    )

    biography = TextAreaField(
        'Дополнительная информация',
        validators=[Optional(), Length(max=2000)],
        render_kw={"placeholder": "Биография, достижения...", "rows": 4}
    )

    # Раздельные поля для разных типов связей (можно заполнять все одновременно)
    spouses_ids = SelectMultipleField(
        'Супруг(и)',
        choices=[],
        validators=[Optional()]
    )

    parents_ids = SelectMultipleField(
        'Родители (максимум 2)',
        choices=[],
        validators=[Optional()]
    )

    children_ids = SelectMultipleField(
        'Дети',
        choices=[],
        validators=[Optional()]
    )

    submit = SubmitField('Добавить родственника')