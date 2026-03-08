ROLE_ADMIN = "inventory_admin"
ROLE_STOREKEEPER = "inventory_storekeeper"
ROLE_VIEWER = "inventory_viewer"

def bootstrap_roles():
    """
    Создает группы и выдает права:
      - viewer: только просмотр
      - storekeeper: просмотр + изменение оборудования/сотрудников + создание документов
      - admin: все права inventory (+ можно назначить is_staff/is_superuser отдельно)
    """
    from django.contrib.auth.models import Group, Permission
    from django.apps import apps

    inventory_models = [
        apps.get_model("inventory", "Equipment"),
        apps.get_model("inventory", "Employee"),
        apps.get_model("inventory", "EquipmentEvent"),
        apps.get_model("inventory", "InventoryDocument"),
        apps.get_model("inventory", "InventoryDocumentLine"),
        apps.get_model("inventory", "Organization"),
        apps.get_model("inventory", "Department"),
        apps.get_model("inventory", "EquipmentType"),
    ]

    def perms_for(model, actions):
        # actions: view/add/change/delete
        ct = model._meta.app_label, model._meta.model_name
        res = []
        for a in actions:
            codename = f"{a}_{ct[1]}"
            try:
                res.append(Permission.objects.get(content_type__app_label=ct[0], codename=codename))
            except Permission.DoesNotExist:
                pass
        return res

    viewer, _ = Group.objects.get_or_create(name=ROLE_VIEWER)
    storekeeper, _ = Group.objects.get_or_create(name=ROLE_STOREKEEPER)
    admin, _ = Group.objects.get_or_create(name=ROLE_ADMIN)

    # viewer: view на все
    viewer_perms = []
    for m in inventory_models:
        viewer_perms += perms_for(m, ["view"])
    viewer.permissions.set(viewer_perms)

    # storekeeper: view + add/change на ключевые сущности (без delete по умолчанию)
    storekeeper_perms = []
    for m in inventory_models:
        storekeeper_perms += perms_for(m, ["view"])
    for m in [apps.get_model("inventory", "Equipment"),
              apps.get_model("inventory", "Employee"),
              apps.get_model("inventory", "InventoryDocument"),
              apps.get_model("inventory", "InventoryDocumentLine"),
              apps.get_model("inventory", "EquipmentEvent")]:
        storekeeper_perms += perms_for(m, ["add", "change"])
    storekeeper.permissions.set(list({p.id: p for p in storekeeper_perms}.values()))

    # admin: все perms inventory
    admin_perms = []
    for m in inventory_models:
        admin_perms += perms_for(m, ["view", "add", "change", "delete"])
    admin.permissions.set(list({p.id: p for p in admin_perms}.values()))