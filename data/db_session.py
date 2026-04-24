import sqlalchemy as sa
import sqlalchemy.orm as orm
from sqlalchemy.orm import Session
from contextlib import contextmanager

SqlAlchemyBase = orm.declarative_base()

__factory = None

def global_init(db_file):
    global __factory

    if __factory:
        return

    if not db_file or not db_file.strip():
        raise Exception("Необходимо указать файл базы данных.")

    conn_str = f'sqlite:///{db_file.strip()}?check_same_thread=False'
    print(f"Подключение к базе данных по адресу {conn_str}")

    # НАСТРОЙКИ ПУЛА СОЕДИНЕНИЙ ДЛЯ SQLite
    # SQLite не поддерживает традиционный пул, но эти настройки помогут
    engine = sa.create_engine(
        conn_str,
        echo=False,
        pool_size=20,           # Размер пула (макс. постоянных соединений)
        max_overflow=40,        # Дополнительные соединения при нагрузке
        pool_timeout=60,        # Таймаут ожидания соединения (секунды)
        pool_recycle=3600,      # Пересоздавать соединения каждый час
        pool_pre_ping=True      # Проверять соединение перед использованием
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