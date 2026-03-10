from asgiref.sync import sync_to_async
from django.db import transaction
from apps.directory.access import get_allowed_organizations
from apps.directory.models import Department, Employee, Organization
from apps.inventory.models import Equipment, EquipmentEvent, EquipmentEventType, EquipmentType
from apps.users.models import User

# -----Список доступных организаций для User
def access_orgs_for_user(telegram_id):
    user = User.objects.filter(telegram_id=telegram_id, is_active=True).first()
    if not user:
        return None

    orgs = get_allowed_organizations(user)

    if user.is_superuser:
        return None

    return list(orgs.values_list("id", flat=True))

    # admin_emp = Employee.objects.filter(telegram_id=telegram_id, is_admin=True, is_approved=True).first()
    # if not admin_emp:
    #     return None
    #
    # try:
    #     admin_scope_model = apps.get_model('core', 'AdminScope')
    # except LookupError:
    #     return None
    #
    # scope = admin_scope_model.objects.filter(employee=admin_emp).prefetch_related('allowed_regions').first()
    # if not scope or scope.can_manage_all_regions:
    #     return None
    #
    # return list(scope.allowed_regions.values_list('id', flat=True))

# ---------- Базовые функции (используются в start.py и др.) ----------
# получить по id телеграмма пользователя
@sync_to_async
def get_user_by_telegram(telegram_id):
    try:
        return User.objects.get(telegram_id=telegram_id, is_active=True)
    except User.DoesNotExist:
        return None
    # try:
    #     return Employee.objects.select_related('department').get(telegram_id=telegram_id, is_approved=True)
    # except Employee.DoesNotExist:
    #     return None

# получить по qr оборудование
@sync_to_async
def get_device_by_qr_code(code):
    try:
        return (
            Equipment.objects
            .select_related('organization', 'assigned_to', 'equipment_type')
            .get(qr_token=code, is_active=True)
        )
    except Equipment.DoesNotExist:
        return None
    # try:
    #     qr = QRCode.objects.select_related('device__responsible', 'device__department', 'device__device_type').get(code=code, is_active=True)
    #     return qr.device
    # except QRCode.DoesNotExist:
    #     return None

# получить по qr или id оборудование
@sync_to_async
def get_device_by_code_or_id(identifier):
    qs = Equipment.objects.select_related(
        "organization",
        "equipment_type",
        "assigned_to",
    )

    try:
        equipment_id = int(identifier)
        equipment = qs.filter(id=equipment_id).first()
        if equipment:
            return equipment
    except (ValueError, TypeError):
        pass
    return qs.filter(qr_token=identifier).first()
    # try:
    #     qr_id = int(identifier)
    #     qr = QRCode.objects.select_related('device__responsible', 'device__department', 'device__device_type').filter(id=qr_id, is_active=True).first()
    #     if qr:
    #         return qr.device
    # except ValueError:
    #     pass
    # try:
    #     qr = QRCode.objects.select_related('device__responsible', 'device__department', 'device__device_type').get(code=identifier, is_active=True)
    #     return qr.device
    # except QRCode.DoesNotExist:
    #     return None

# получить оборудование за пользователем
@sync_to_async
def get_employee_devices(employee):
    return list(employee.assigned_equipment.select_related(
        "equipment_type",
        "organization"
    ).all())
    # return list(employee.devices.select_related('device_type', 'department').all())

# получить список оборудования по фильтру
@sync_to_async
def get_all_devices_filtered(organization_id=None, equipment_type_id=None, status=None, admin_telegram_id=None):
    qs = Equipment.objects.select_related(
        'organization',
        'equipment_type',
        'assigned_to'
    ).all()

    if admin_telegram_id is not None:
        org_ids = access_orgs_for_user(admin_telegram_id)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)

    if organization_id and organization_id != "all":
        qs = qs.filter(organization_id=organization_id)

    if equipment_type_id and equipment_type_id != "all":
        qs = qs.filter(equipment_type_id=equipment_type_id)

    if status is not None and status != "all":
        qs = qs.filter(status=status)

    return list(qs)

    # qs = Device.objects.select_related('department', 'region', 'device_type', 'responsible').all()
    # if admin_telegram_id is not None:
    #     region_ids = _region_filter_for_admin(admin_telegram_id)
    #     if region_ids is not None:
    #         qs = qs.filter(region_id__in=region_ids)
    # if department_id and department_id != 'all':
    #     qs = qs.filter(department_id=department_id)
    # if device_type_id and device_type_id != 'all':
    #     qs = qs.filter(device_type_id=device_type_id)
    # if status is not None and status != 'all':
    #     qs = qs.filter(status=(status == 'active'))
    # return list(qs)

# получить список подразделений
@sync_to_async
def get_departments(admin_telegram_id=None):
    qs = Department.objects.all()
    if admin_telegram_id is not None:
        region_ids = access_orgs_for_user(admin_telegram_id)
        if region_ids is not None:
            qs = qs.filter(region_id__in=region_ids)
    return list(qs)
    # qs = Department.objects.all()
    # if admin_telegram_id is not None:
    #     region_ids = _region_filter_for_admin(admin_telegram_id)
    #     if region_ids is not None:
    #         qs = qs.filter(region_id__in=region_ids)
    # return list(qs)
@sync_to_async
def get_department_by_id(dept_id):
    return Department.objects.get(id=dept_id)

# получить список Типы оборудования
@sync_to_async
def get_device_types():
    qs = EquipmentType.objects.all()
    return list(qs)
    # return list(DeviceType.objects.all())

# проверка администратор ли пользователь
@sync_to_async
def is_admin(telegram_id):
    # return User.objects.filter(telegram_id=telegram_id, is_admin=True, is_approved=True).exists()
    return User.objects.filter(telegram_id=telegram_id, is_active=True).exists()


# ---------- Функции для сотрудников ----------
# Создание сотрудника
@sync_to_async
def create_employee(full_name, department_id=None, organization_id=None, **kwargs):
    employee = Employee.objects.create(
        full_name=full_name,
        department_id=department_id,
        organization_id=organization_id,
        is_active=True,
        # is_approved=is_approved,
        # telegram_id=telegram_id,
        **kwargs
    )
    return employee
    # employee = Employee.objects.create(
    #     full_name=full_name,
    #     department_id=department_id,
    #     is_approved=is_approved,
    #     telegram_id=telegram_id,
    #     **kwargs
    # )
    # return employee

# получение списка сотрудников
@sync_to_async
def get_all_employees():
    return list(Employee.objects.all().order_by('full_name'))

# получение списка доступных сотрудников
@sync_to_async
def get_all_employees_data(admin_telegram_id=None):
    qs = Employee.objects.select_related("organization", "department")

    if admin_telegram_id is not None:
        org_ids = access_orgs_for_user(admin_telegram_id)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)

    return list(
        qs.order_by("full_name").values(
            "id",
            "full_name",
            "active",
            "department__name",
            "organization__name",
        )
    )
    # qs = Employee.objects.select_related('organization')
    # if admin_telegram_id is not None:
    #     region_ids = _region_filter_for_admin(admin_telegram_id)
    #     if region_ids is not None:
    #         qs = qs.filter(department__region_id__in=region_ids)
    # return list(qs.order_by('full_name').values('id', 'full_name', 'is_approved', 'department__name'))

# получение списка доступных сотрудников по подразделению
@sync_to_async
def get_all_employees_with_dept(admin_telegram_id=None, department_id=None):
    qs = Employee.objects.select_related("department", "organization").all()

    if department_id is not None:
        qs = qs.filter(department_id=department_id)

    if admin_telegram_id is not None:
        org_ids = access_orgs_for_user(admin_telegram_id)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)

    return list(qs.order_by("full_name"))
    # qs = Employee.objects.select_related('department').all()
    # if department_id is not None:
    #     qs = qs.filter(department_id=department_id)
    # if admin_telegram_id is not None:
    #     region_ids = _region_filter_for_admin(admin_telegram_id)
    #     if region_ids is not None:
    #         qs = qs.filter(department__region_id__in=region_ids)
    # return list(qs.order_by('full_name'))

# получение списка доступных организаций
@sync_to_async
def get_all_organization(admin_telegram_id=None):
    qs = Organization.objects.filter(is_active=True)
    if admin_telegram_id is not None:
        org_ids = access_orgs_for_user(admin_telegram_id)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)
    return list(qs.order_by("organization__name"))

# получение списка доступных подразделений
@sync_to_async
def get_all_departments(admin_telegram_id=None):
    qs = Department.objects.filter(is_active=True)
    if admin_telegram_id is not None:
        org_ids = access_orgs_for_user(admin_telegram_id)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)
    return list(qs.order_by("department__name"))

    # qs = Department.objects.all()
    # if admin_telegram_id is not None:
    #     region_ids = _region_filter_for_admin(admin_telegram_id)
    #     if region_ids is not None:
    #         qs = qs.filter(region_id__in=region_ids)
    # return list(qs)

# получение списка доступных сотрудников по подразделению
# есть get_all_employees_with_dept надо разобраться
@sync_to_async
def get_employees_by_department(department_id, admin_telegram_id=None):
    qs = Employee.objects.filter(department_id=department_id, active=True)
    if admin_telegram_id is not None:
        org_ids = access_orgs_for_user(admin_telegram_id)
        if org_ids is not None:
            qs = qs.filter(department__organization_id__in=org_ids)
    return list(qs.order_by("full_name"))

    # qs = Employee.objects.filter(department_id=department_id).select_related('department')
    # if admin_telegram_id is not None:
    #     region_ids = _region_filter_for_admin(admin_telegram_id)
    #     if region_ids is not None:
    #         qs = qs.filter(department__region_id__in=region_ids)
    # return list(qs.order_by('full_name'))

# возможно не надо
# @sync_to_async
# def get_employee_data(employee_id):
#     try:
#         return Employee.objects.select_related("department", "organization").get(id=employee_id)
#     except Employee.DoesNotExist:
#         return None

# получаем сотрудника по employee_id
@sync_to_async
def get_employee_data_safe(employee_id):
    try:
        emp = Employee.objects.select_related('department','organization').get(id=employee_id)
        return {
            'id': emp.id,
            'full_name': emp.full_name,
            "organization_id": emp.organization_id,
            "organization_name": emp.organization.name,
            "department_id": emp.department_id,
            "department_name": emp.department.name,
            "active": emp.active,
            "email": emp.email,
            "phone": emp.phone,
            # 'is_approved': emp.is_approved,
            # 'telegram_id': emp.telegram_id,
        }
    except Employee.DoesNotExist:
        return None

# редактируем сотрудника по employee_id
@sync_to_async
def update_employee(employee_id, full_name=None, department_id=None, organization_id=None, active=None, email=None, phone=None):
    try:
        emp = Employee.objects.get(id=employee_id)

        if full_name is not None:
            emp.full_name = full_name
        if department_id is not None:
            emp.department_id = department_id
        if organization_id is not None:
            emp.organization_id = organization_id
        if active is not None:
            emp.active = active
        if email is not None:
            emp.email = email
        if phone is not None:
            emp.phone = phone

        emp.save()
        return emp
    except Employee.DoesNotExist:
        return None

# @sync_to_async
# def update_employee(employee_id, full_name=None, department_id=None, is_approved=None, telegram_id=...):
#
    # try:
    #     emp = Employee.objects.get(id=employee_id)
    #     if full_name is not None:
    #         emp.full_name = full_name
    #     if department_id is not None:
    #         emp.department_id = department_id
    #     if is_approved is not None:
    #         emp.is_approved = is_approved
    #     if telegram_id is not ...:
    #         emp.telegram_id = telegram_id
    #     emp.save()
    #     return emp
    # except Employee.DoesNotExist:
    #     return None

# делаем не активным сотрудника по employee_id
@sync_to_async
def delete_employee(employee_id):
    try:
        emp = Employee.objects.get(id=employee_id)
        emp.active = False
        emp.save(update_fields=["active"])
        return True
    except Employee.DoesNotExist:
        return False

# получаем список оборудования за сотрудником по employee_id
@sync_to_async
def get_employee_devices(employee_id):
    try:
        device_epm = Equipment.objects.filter(assigned_to=employee_id).select_related('equipment_type', 'organization').all()
        return list(device_epm)
    except Employee.DoesNotExist:
        return []

# получаем оборудование по id
@sync_to_async
def get_device_by_id(id):
    try:
        return Equipment.objects.select_related(
            'equipment_type',
            'organization',
            'assigned_to'
        ).get(id=id)
    except Equipment.DoesNotExist:
        return None
    # try:
    #     return QRCode.objects.get(id=qr_id)
    # except QRCode.DoesNotExist:
    #     return None

# получаем оборудование по qr или id
@sync_to_async
def get_qr_data(qr_id):
    try:
        return Equipment.objects.select_related(
            'equipment_type',
            'organization',
            'assigned_to'
        ).get(qr_token=qr_id)
    except Equipment.DoesNotExist:
        return None

# список оборудования
@sync_to_async
def get_all_devices(admin_telegram_id=None):
    qs = Equipment.objects.select_related('equipment_type', 'organization','assigned_to').all()
    if admin_telegram_id is not None:
        org_ids = access_orgs_for_user(admin_telegram_id)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)
    return list(qs.order_by("full_name"))

    # from apps.core.models import Device
    # qs = Device.objects.select_related('department', 'responsible').all()
    # if admin_telegram_id is not None:
    #     region_ids = _region_filter_for_admin(admin_telegram_id)
    #     if region_ids is not None:
    #         qs = qs.filter(region_id__in=region_ids)
    # return list(qs.order_by('inventory_number'))

# оборудование по device_id
@sync_to_async
def get_device_data(device_id, admin_telegram_id=None):
    qs = Equipment.objects.select_related('equipment_type', 'organization', 'assigned_to').all()
    if admin_telegram_id is not None:
        org_ids = access_orgs_for_user(admin_telegram_id)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)
    try:
        return qs.get(id=device_id)
    except Equipment.DoesNotExist:
        return None

    # qs = Device.objects.select_related('department', 'responsible', 'device_type')
    # if admin_telegram_id is not None:
    #     region_ids = _region_filter_for_admin(admin_telegram_id)
    #     if region_ids is not None:
    #         qs = qs.filter(region_id__in=region_ids)
    # try:
    #     return qs.get(id=device_id)
    # except Device.DoesNotExist:
    #     return None

# перемещение оборудования
@sync_to_async
def change_device_responsible(device_id, new_responsible_id, admin_telegram_id=None, document_number="", comment=""):
    with transaction.atomic():
        try:
            equipment = Equipment.objects.select_related(
                "organization", "assigned_to"
            ).get(id=device_id)

            employee = Employee.objects.select_related(
                "organization", "department"
            ).get(id=new_responsible_id, active=True)

        except (Equipment.DoesNotExist, Employee.DoesNotExist):
            return False, "Оборудование или сотрудник не найдены", None

        if admin_telegram_id is not None:
            org_ids = access_orgs_for_user(admin_telegram_id)
            if org_ids is not None:
                if equipment.organization_id not in org_ids or employee.organization_id not in org_ids:
                    return False, "Нет доступа к выбранной организации", None

        if equipment.organization_id != employee.organization_id:
            return False, "Сотрудник и оборудование должны быть из одной организации", None

        old_responsible = equipment.assigned_to
        # old_department = equipment.department
        old_status = getattr(equipment, "status", "") or ""
        event_type = EquipmentEventType.MOVE

        if equipment.assigned_to == employee.id:
            return True, "Ответственный уже назначен", {
                "equipment": equipment,
                # "from_department": old_department.name if old_department else "—",
                # "to_department": equipment.department.name if equipment.department else "—",
                "from_responsible": old_responsible.full_name if old_responsible else "—",
                "to_responsible": employee.full_name,
                "event_id": None,
            }

        update_fields = ["assigned_to"]
        equipment.assigned_to = employee

        if hasattr(equipment, "organization_id") and equipment.organization_id != employee.organization_id:
            equipment.organization_id = employee.organization_id
            update_fields.append("organization")

        equipment.save(update_fields=update_fields)

        event = EquipmentEvent.objects.create(
            equipment=equipment,
            event_type=event_type,
            from_employee=old_responsible,
            to_employee=employee,
            old_status=old_status,
            new_status=getattr(equipment, "status", "") or "",
            document_number=document_number,
            comment=comment,
        )

        movement_info = {
            "equipment": equipment,
            # "from_department": old_department.name if old_department else "—",
            # "to_department": equipment.department.name if equipment.department else "—",
            "from_responsible": old_responsible.full_name if old_responsible else "—",
            "to_responsible": employee.full_name,
            "event_id": event.id,
        }

        return True, "Ответственный успешно изменён", movement_info


    # try:
    #     device = Device.objects.select_related('department', 'responsible').get(id=device_id)
    #     employee = Employee.objects.select_related('department').get(id=new_responsible_id)
    # except (Device.DoesNotExist, Employee.DoesNotExist):
    #     return False, 'Устройство или сотрудник не найдены', None
    #
    # if admin_telegram_id is not None:
    #     region_ids = _region_filter_for_admin(admin_telegram_id)
    #     if region_ids is not None:
    #         dev_region = device.region_id or (device.department.region_id if device.department else None)
    #         emp_region = employee.department.region_id if employee.department else None
    #         if (dev_region and dev_region not in region_ids) or (emp_region and emp_region not in region_ids):
    #             return False, 'Нет доступа к выбранному региону', None
    #
    # old_responsible = device.responsible
    # old_department = device.department
    #
    # device.responsible = employee
    # if employee.department and employee.department != device.department:
    #     device.department = employee.department
    # device.save()
    #
    # device.refresh_from_db(fields=['department', 'responsible'])
    # from apps.core.models import MovementCard
    # card = MovementCard.objects.filter(history__device=device, history__field='responsible').order_by('-created_at').first()
    # movement_info = {
    #     'device': device,
    #     'from_department': old_department.name if old_department else '—',
    #     'to_department': device.department.name if device.department else '—',
    #     'from_responsible': old_responsible.full_name if old_responsible else '—',
    #     'to_responsible': device.responsible.full_name if device.responsible else '—',
    #     'card_id': card.id if card else None,
    # }
    # return True, 'Ответственный успешно изменён', movement_info

# получить оборудование с qr
# не надо
# @sync_to_async
# def get_devices_without_qr(admin_telegram_id=None):
#     qs = Equipment.objects.filter(qr_token__isnull=True).select_related('equipment_type','organization','assigned_to')
#     if admin_telegram_id is not None:
#         org_ids = _access_orgs_for_user(admin_telegram_id)
#         if org_ids is not None:
#             qs = qs.filter(organization_id__in=org_ids)
#     return list(qs.order_by("inventory_number"))

    # from apps.core.models import Device
    # qs = Device.objects.filter(qr_code__isnull=True).select_related('department', 'region', 'responsible')
    # if admin_telegram_id is not None:
    #     region_ids = _region_filter_for_admin(admin_telegram_id)
    #     if region_ids is not None:
    #         qs = qs.filter(region_id__in=region_ids)
    # return list(qs.order_by('inventory_number'))


@sync_to_async
def update_device_status(device_id, status, admin_telegram_id=None):
    if status not in {'in_use', 'repair', 'reserve', 'to_transfer', 'to_write_off', 'written_off'}:
        return False, 'Некорректный статус'

    qs = Equipment.objects.all()
    if admin_telegram_id is not None:
        org_ids = access_orgs_for_user(admin_telegram_id)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)

    device = qs.filter(id=device_id).first()
    if not device:
        return False, 'Техника не найдена или нет доступа'

    device.status = status
    device.save(update_fields=['status'])
    return True, f'Статус обновлён: {device.inventory_number} — {device.get_status_display()}'
