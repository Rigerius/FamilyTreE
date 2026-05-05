import datetime
import sqlalchemy
from .db_session import SqlAlchemyBase


class Family(SqlAlchemyBase):
    __tablename__ = 'families'

    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    family_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    status = sqlalchemy.Column(sqlalchemy.Boolean, nullable=True)
    creator = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # ID создателя
    editors = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # JSON список редакторов
    members = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # JSON список участников (все)
    persons = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    data = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)
    created_date = sqlalchemy.Column(sqlalchemy.DateTime,
                                     default=datetime.datetime.now)

    def get_members_list(self):
        """Получить список всех участников"""
        import json
        return json.loads(self.members) if self.members else []

    def get_editors_list(self):
        """Получить список редакторов"""
        import json
        return json.loads(self.editors) if self.editors else []

    def is_creator(self, user_id):
        """Проверить, является ли пользователь создателем"""
        return self.creator == str(user_id)

    def is_editor(self, user_id):
        """Проверить, имеет ли пользователь права редактора"""
        return str(user_id) in self.get_editors_list()

    def is_member(self, user_id):
        """Проверить, является ли пользователь участником"""
        return str(user_id) in self.get_members_list()

    def can_edit(self, user_id):
        """Может ли пользователь редактировать (создатель или редактор)"""
        return self.is_creator(user_id) or self.is_editor(user_id)

    def can_view(self, user_id):
        """Может ли пользователь просматривать"""
        return self.is_member(user_id) or self.status  # Публичные семьи видят все