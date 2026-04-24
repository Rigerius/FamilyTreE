import datetime
import sqlalchemy
from .db_session import SqlAlchemyBase


class Family(SqlAlchemyBase):
    __tablename__ = 'families'

    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True, nullable=True)
    family_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    status = sqlalchemy.Column(sqlalchemy.Boolean, nullable=True)
    creator = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    editors = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    members = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    persons = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    data = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)
    created_date = sqlalchemy.Column(sqlalchemy.DateTime,
                                     default=datetime.datetime.now)