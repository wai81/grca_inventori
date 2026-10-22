ROLE_ADMIN = "inventory_admin"
ROLE_STOREKEEPER = "inventory_storekeeper"
ROLE_VIEWER = "inventory_viewer"

ALL_MODELS = [
    "inventory.Equipment",
    "inventory.EquipmentEvent",
    "inventory.InventoryDocument",
    "inventory.InventoryDocumentLine",
    "inventory.EquipmentType",
    "directory.Organization",
    "directory.Department",
    "directory.Employee",
]

# модели, которые кладовщик может создавать и изменять
STOREKEEPER_EDIT_MODELS = [
    "inventory.Equipment",
    "inventory.EquipmentEvent",
    "inventory.InventoryDocument",
    "inventory.InventoryDocumentLine",
    "directory.Department",
    "directory.Employee",
]


def bootstrap_roles():
    """
    Создает группы и выдает права:
      - viewer: только просмотр
      - storekeeper: просмотр + изменение оборудования/сотрудников/подразделений + создание документов
      - admin: все права inventory и directory (+ можно назначить is_staff/is_superuser отдельно)
    Возвращает словарь {имя роли: Group}.
    """
    from django.apps import apps
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType

    def perms_for(labels, actions):
        res = []
        for label in labels:
            model = apps.get_model(label)
            ct = ContentType.objects.get_for_model(model)
            codenames = [f"{a}_{model._meta.model_name}" for a in actions]
            res += list(Permission.objects.filter(content_type=ct, codename__in=codenames))
        return res

    viewer, _ = Group.objects.get_or_create(name=ROLE_VIEWER)
    storekeeper, _ = Group.objects.get_or_create(name=ROLE_STOREKEEPER)
    admin, _ = Group.objects.get_or_create(name=ROLE_ADMIN)

    viewer.permissions.set(perms_for(ALL_MODELS, ["view"]))
    storekeeper.permissions.set(
        perms_for(ALL_MODELS, ["view"]) + perms_for(STOREKEEPER_EDIT_MODELS, ["add", "change"]))
    admin.permissions.set(perms_for(ALL_MODELS, ["view", "add", "change", "delete"]))

    return {ROLE_VIEWER: viewer, ROLE_STOREKEEPER: storekeeper, ROLE_ADMIN: admin}
