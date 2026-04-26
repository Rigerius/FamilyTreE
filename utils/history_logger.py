from data import db_session
from data.history import History
from datetime import datetime
import json


class HistoryLogger:
    """Класс для логирования действий в семье"""

    @staticmethod
    def log_action(family_id, user_id, user_name, action_type, action_description,
                   entity_type=None, entity_id=None, old_data=None, new_data=None):
        """Запись действия в историю"""
        db_sess = db_session.create_session()
        try:
            history = History()
            history.family_id = family_id
            history.user_id = str(user_id)
            history.user_name = user_name
            history.action_type = action_type
            history.action_description = action_description
            history.entity_type = entity_type
            history.entity_id = str(entity_id) if entity_id else None

            # Конвертируем сложные объекты в JSON
            if old_data:
                history.old_data = json.loads(json.dumps(old_data, default=str))
            if new_data:
                history.new_data = json.loads(json.dumps(new_data, default=str))

            db_sess.add(history)
            db_sess.commit()
        except Exception as e:
            print(f"Ошибка при логировании: {e}")
            db_sess.rollback()
        finally:
            db_sess.close()

    # Вспомогательные методы для разных типов действий

    @staticmethod
    def log_family_created(family_id, user_id, user_name, family_name):
        """Логирование создания семьи"""
        HistoryLogger.log_action(
            family_id=family_id,
            user_id=user_id,
            user_name=user_name,
            action_type="family_created",
            action_description=f"Создана семья '{family_name}'",
            entity_type="family",
            entity_id=family_id
        )

    @staticmethod
    def log_family_edited(family_id, user_id, user_name, old_name, new_name):
        """Логирование редактирования семьи"""
        HistoryLogger.log_action(
            family_id=family_id,
            user_id=user_id,
            user_name=user_name,
            action_type="family_edited",
            action_description=f"Семья переименована из '{old_name}' в '{new_name}'",
            entity_type="family",
            entity_id=family_id,
            old_data={"name": old_name},
            new_data={"name": new_name}
        )

    @staticmethod
    def log_person_added(family_id, user_id, user_name, person_id, person_name, relations=None):
        """Логирование добавления родственника"""
        desc = f"Добавлен родственник '{person_name}'"
        if relations:
            desc += f" со связями: {', '.join(relations)}"

        HistoryLogger.log_action(
            family_id=family_id,
            user_id=user_id,
            user_name=user_name,
            action_type="person_added",
            action_description=desc,
            entity_type="person",
            entity_id=person_id,
            new_data={"name": person_name, "relations": relations}
        )

    @staticmethod
    def log_person_edited(family_id, user_id, user_name, person_id, old_name, new_name):
        """Логирование редактирования родственника"""
        HistoryLogger.log_action(
            family_id=family_id,
            user_id=user_id,
            user_name=user_name,
            action_type="person_edited",
            action_description=f"Отредактирован родственник '{new_name}'",
            entity_type="person",
            entity_id=person_id,
            old_data={"name": old_name},
            new_data={"name": new_name}
        )

    @staticmethod
    def log_person_deleted(family_id, user_id, user_name, person_id, person_name):
        """Логирование удаления родственника"""
        HistoryLogger.log_action(
            family_id=family_id,
            user_id=user_id,
            user_name=user_name,
            action_type="person_deleted",
            action_description=f"Удалён родственник '{person_name}'",
            entity_type="person",
            entity_id=person_id,
            old_data={"name": person_name}
        )

    @staticmethod
    def log_member_added(family_id, user_id, user_name, new_member_name):
        """Логирование добавления участника в семью"""
        HistoryLogger.log_action(
            family_id=family_id,
            user_id=user_id,
            user_name=user_name,
            action_type="member_added",
            action_description=f"Добавлен участник '{new_member_name}'",
            entity_type="family",
            entity_id=family_id,
            new_data={"member": new_member_name}
        )

    @staticmethod
    def log_member_removed(family_id, user_id, user_name, removed_member_name):
        """Логирование удаления участника из семьи"""
        HistoryLogger.log_action(
            family_id=family_id,
            user_id=user_id,
            user_name=user_name,
            action_type="member_removed",
            action_description=f"Удалён участник '{removed_member_name}'",
            entity_type="family",
            entity_id=family_id,
            old_data={"member": removed_member_name}
        )