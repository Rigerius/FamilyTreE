import datetime
import sqlalchemy
from .db_session import SqlAlchemyBase

class History(SqlAlchemyBase):
    __tablename__ = 'history'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    family_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    user_id = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    user_name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    action_type = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    action_description = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    entity_type = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    entity_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    old_data = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)
    new_data = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.datetime.now)