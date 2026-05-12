from flask_login import current_user


def is_admin():
    """Проверка, является ли текущий пользователь администратором"""
    return current_user.is_authenticated and current_user.is_admin


def can_view_family(family, current_user):
    if current_user.is_authenticated and current_user.is_admin:
        return True

    # Для неадминистраторов - обычная проверка
    from data import db_session
    import json

    is_public = family.status == True

    if current_user.is_authenticated:
        members = json.loads(family.members) if family.members else []
        is_member = str(current_user.id) in members
        return is_public or is_member

    return is_public