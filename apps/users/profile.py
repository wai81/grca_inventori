from django.utils.functional import SimpleLazyObject

from apps.directory.access import get_allowed_organizations
from apps.inventory.roles import ROLE_ADMIN, ROLE_STOREKEEPER, ROLE_VIEWER

ROLE_LABELS = {
    ROLE_ADMIN: "Администратор",
    ROLE_STOREKEEPER: "Кладовщик",
    ROLE_VIEWER: "Просмотр",
}

# разделы для таблицы прав: (название, app_label, model_name)
PERMISSION_AREAS = [
    ("Оборудование", "inventory", "equipment"),
    ("Акты", "inventory", "inventorydocument"),
    ("Типы оборудования", "inventory", "equipmenttype"),
    ("Сотрудники", "directory", "employee"),
    ("Подразделения", "directory", "department"),
    ("Организации", "directory", "organization"),
]
PERMISSION_ACTIONS = [("view", "Просмотр"), ("add", "Создание"), ("change", "Изменение"), ("delete", "Удаление")]


def initials(user):
    parts = [p for p in (user.last_name, user.first_name) if p]
    if not parts:
        parts = [user.get_username()]
    return "".join(p[0] for p in parts[:2]).upper()


def build_profile(user):
    """Сводка о пользователе для меню профиля и страницы профиля."""
    if user.is_superuser:
        roles = ["Суперпользователь"]
    else:
        roles = [ROLE_LABELS.get(g.name, g.name) for g in user.groups.all()] or ["Без роли"]

    orgs = list(get_allowed_organizations(user).order_by("code"))

    return {
        "display_name": user.get_full_name() or user.get_username(),
        "initials": initials(user),
        "roles": roles,
        "role": roles[0],
        "organizations": orgs,
        "all_organizations": user.is_superuser,
        "telegram_linked": bool(user.telegram_id),
    }


def permission_table(user):
    rows = []
    for title, app, model in PERMISSION_AREAS:
        rows.append({
            "title": title,
            "actions": [user.has_perm(f"{app}.{action}_{model}") for action, _ in PERMISSION_ACTIONS],
        })
    return rows


def user_profile(request):
    """Context processor: {{ profile }} — ленивые данные о текущем пользователе."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    return {"profile": SimpleLazyObject(lambda: build_profile(user))}
