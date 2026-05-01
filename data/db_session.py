import sqlalchemy as sa
import sqlalchemy.orm as orm
from sqlalchemy.orm import Session
from contextlib import contextmanager
import sqlite3
import os

SqlAlchemyBase = orm.declarative_base()

__factory = None


def check_and_migrate_db(db_file):
    """Проверяет и добавляет недостающие колонки в базу данных"""
    if not os.path.exists(db_file):
        return

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Проверяем колонку avatar в таблице users
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'avatar' not in columns:
            print("Миграция: добавляем колонку avatar в таблицу users...")
            cursor.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
            conn.commit()
            print("Миграция успешно выполнена!")

        conn.close()
    except Exception as e:
        print(f"Ошибка при миграции: {e}")


def global_init(db_file):
    global __factory

    if __factory:
        return

    if not db_file or not db_file.strip():
        raise Exception("Необходимо указать файл базы данных.")

    # Проверяем и обновляем структуру БД перед созданием engine
    check_and_migrate_db(db_file.strip())

    conn_str = f'sqlite:///{db_file.strip()}?check_same_thread=False'
    print(f"Подключение к базе данных по адресу {conn_str}")

    engine = sa.create_engine(
        conn_str,
        echo=False,
        pool_size=20,
        max_overflow=40,
        pool_timeout=60,
        pool_recycle=3600,
        pool_pre_ping=True
    )
    __factory = orm.sessionmaker(bind=engine)

    from . import __all_models

    SqlAlchemyBase.metadata.create_all(engine)


def create_session() -> Session:
    global __factory
    if not __factory:
        raise Exception("Вы должны вызвать global_init() перед созданием сессии")
    return __factory()


@contextmanager
def session_scope():
    """Контекстный менеджер для автоматического закрытия сессии"""
    session = create_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()