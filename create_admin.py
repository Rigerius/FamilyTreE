import os
import sys
from data import db_session
from data.users import User


def create_admin():
    """Создание первого администратора"""
    db_session.global_init("db/database_2.db")
    db_sess = db_session.create_session()

    # Проверяем, есть ли уже администраторы
    admin_exists = db_sess.query(User).filter(User.is_admin == True).first()

    if admin_exists:
        print(f"Администратор уже существует: {admin_exists.name}")
        return

    # Создаём администратора
    admin = User()
    admin.name = input("Введите имя администратора: ")
    admin.email = input("Введите email администратора: ")
    admin.is_admin = True

    password = input("Введите пароль: ")
    admin.set_password(password)

    db_sess.add(admin)
    db_sess.commit()

    print(f"Администратор {admin.name} успешно создан!")


if __name__ == '__main__':
    create_admin()