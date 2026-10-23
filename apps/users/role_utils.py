"""Роли = группы Django. Системные роли (inventory_*) создаёт bootstrap_roles, остальные — пользовательские."""
from django.contrib.auth.models import Group, Permission
from django.db.models import Count, Q

from apps.inventory.roles import ROLE_ADMIN, ROLE_STOREKEEPER, ROLE_VIEWER

from .profile import PERMISSION_ACTIONS, PERMISSION_AREAS, ROLE_LABELS

SYSTEM_ROLES = (ROLE_VIEWER, ROLE_STOREKEEPER, ROLE_ADMIN)

# служебные модели, права на которые следуют за разделом
AREA_COMPANIONS = {
    ("inventory", "equipment"): [("inventory", "equipmentevent")],
    ("inventory", "inventorydocument"): [("inventory", "inventorydocumentline")],
}


def role_label(name):
    return ROLE_LABELS.get(name, name)


def is_system(group_or_name):
    name = getattr(group_or_name, "name", group_or_name)
    return name in SYSTEM_ROLES


def role_css(name):
    """Модификатор CSS для плашки роли."""
    if not name:
        return "none"
    return name if is_system(name) else "custom"


def ordered_roles(with_counts=False):
    """Все роли: сначала системные по старшинству, затем пользовательские по имени."""
    qs = Group.objects.all()
    if with_counts:
        qs = qs.annotate(users_count=Count("user", filter=Q(user__is_active=True, user__is_superuser=False)))
    order = {name: i for i, name in enumerate(SYSTEM_ROLES)}
    return sorted(qs, key=lambda g: (order.get(g.name, len(order)), g.name.lower()))


def managed_codenames():
    """[(app_label, codename)] всех прав, которыми управляет матрица (включая служебные модели)."""
    result = []
    for _, app, model in PERMISSION_AREAS:
        for action, _ in PERMISSION_ACTIONS:
            for a, m in [(app, model)] + AREA_COMPANIONS.get((app, model), []):
                result.append((a, f"{action}_{m}"))
    return result


def permission_rows(group):
    """Строки матрицы прав для роли: [{title, key, cells: [{action, name, allowed}]}]."""
    codes = set()
    if group is not None and group.pk:
        codes = {(p.content_type.app_label, p.codename)
                 for p in group.permissions.select_related("content_type")}
    rows = []
    for title, app, model in PERMISSION_AREAS:
        rows.append({
            "title": title,
            "cells": [{
                "action": action,
                "label": label,
                "name": f"perm__{app}__{model}__{action}",
                "allowed": (app, f"{action}_{model}") in codes,
            } for action, label in PERMISSION_ACTIONS],
        })
    return rows


def summarize(rows):
    """Короткое описание роли по матрице прав."""
    by_action = {action: [r["title"] for r in rows if r["cells"][i]["allowed"]]
                 for i, (action, _) in enumerate(PERMISSION_ACTIONS)}
    if not any(by_action.values()):
        return "Нет прав — пользователь ничего не увидит"

    def part(title, items):
        if not items:
            return None
        return f"{title}: {'все разделы' if len(items) == len(rows) else ', '.join(items).lower()}"

    edit = sorted(set(by_action["add"]) | set(by_action["change"]), key=[r["title"] for r in rows].index)
    parts = [part("Просмотр", by_action["view"]), part("Изменение", edit), part("Удаление", by_action["delete"])]
    return "; ".join(p for p in parts if p)


def role_cards(with_counts=True):
    """Роли для страниц: label, системная ли, матрица и описание."""
    cards = []
    for g in ordered_roles(with_counts=with_counts):
        rows = permission_rows(g)
        cards.append({
            "group": g,
            "name": g.name,
            "label": role_label(g.name),
            "system": is_system(g),
            "css": role_css(g.name),
            "users": getattr(g, "users_count", None),
            "rows": rows,
            "summary": summarize(rows),
        })
    return cards


def set_role_permissions(group, selected):
    """
    Заменяет права роли в разделах матрицы на selected = {(app, model, action)}.
    Права вне матрицы не трогает; служебные модели получают те же действия, что и раздел.
    """
    managed = managed_codenames()
    wanted = set()
    for app, model, action in selected:
        for a, m in [(app, model)] + AREA_COMPANIONS.get((app, model), []):
            wanted.add((a, f"{action}_{m}"))

    q = Q(pk__in=[])
    for app, codename in managed:
        q |= Q(content_type__app_label=app, codename=codename)
    managed_perms = list(Permission.objects.filter(q).select_related("content_type"))
    managed_ids = {p.pk for p in managed_perms}

    keep = [p for p in group.permissions.all() if p.pk not in managed_ids]
    new = [p for p in managed_perms if (p.content_type.app_label, p.codename) in wanted]
    group.permissions.set(keep + new)
