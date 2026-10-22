import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.directory.models import Department, Employee, Organization, UserOrganizationAccess
from apps.inventory.models import (
    DocumentType, Equipment, EquipmentEvent, EquipmentEventType, EquipmentStatus,
    EquipmentType, InventoryDocument, InventoryDocumentLine, PrintMode)
from apps.inventory.roles import bootstrap_roles
from apps.users.models import User

# Пароль тестовых пользователей (только для локальной разработки)
DEMO_PASSWORD = "demo12345"

ORGANIZATIONS = [
    ("400", "Гродно"),
    ("401", "Лида"),
    ("402", "Волковыск"),
    ("403", "Слоним"),
]

DEPARTMENTS = [
    "Бухгалтерия",
    "Отдел кадров",
    "Служба по работе с заказчиками",
    "Отдел информационных технологий",
    "Юридический отдел",
    "Канцелярия",
]

LAST_NAMES = ["Иванов", "Петров", "Сидоров", "Козлов", "Новиков", "Морозов", "Волков", "Соколов",
              "Лебедев", "Кузнецов", "Попов", "Васильев", "Зайцев", "Павлов", "Семенов", "Голубев"]
FIRST_NAMES = [("Иван", "Ивановна"), ("Пётр", "Петровна"), ("Сергей", "Сергеевна"), ("Андрей", "Андреевна"),
               ("Алексей", "Алексеевна"), ("Дмитрий", "Дмитриевна"), ("Николай", "Николаевна"),
               ("Владимир", "Владимировна")]
FEMALE_FIRST = ["Анна", "Елена", "Ольга", "Татьяна", "Наталья", "Ирина", "Марина", "Светлана"]
MALE_PATRONYMIC = ["Иванович", "Петрович", "Сергеевич", "Андреевич", "Алексеевич", "Дмитриевич",
                   "Николаевич", "Владимирович"]

EQUIPMENT_TYPES = [
    ("PC", EquipmentType.Category.COMPUTER),
    ("Ноутбук", EquipmentType.Category.COMPUTER),
    ("Моноблок", EquipmentType.Category.COMPUTER),
    ("Принтер", EquipmentType.Category.PRINT),
    ("МФУ", EquipmentType.Category.PRINT),
    ("Сканер", EquipmentType.Category.OTHER),
    ("Монитор", EquipmentType.Category.OTHER),
    ("ИБП", EquipmentType.Category.OTHER),
]

MODELS = {
    "PC": ["HP ProDesk 400 G7", "Lenovo ThinkCentre M70s", "Dell OptiPlex 3080"],
    "Ноутбук": ["Lenovo ThinkPad T14", "HP ProBook 450 G8", "Dell Latitude 5520"],
    "Моноблок": ["HP ProOne 440 G6", "Lenovo ThinkCentre M70a"],
    "Принтер": ["HP LaserJet Pro M404dn", "Canon i-SENSYS LBP223dw", "Kyocera ECOSYS P2335d"],
    "МФУ": ["HP LaserJet Pro MFP M428fdn", "Canon i-SENSYS MF445dw", "Kyocera ECOSYS M2540dn"],
    "Сканер": ["Canon DR-C225 II", "Epson WorkForce DS-530"],
    "Монитор": ["Dell P2422H", "LG 24MK430H", "Philips 243V7QDSB"],
    "ИБП": ["APC Back-UPS 650", "Ippon Back Basic 850"],
}
CPUS = ["Intel Core i3-10100", "Intel Core i5-10400", "Intel Core i5-1135G7", "Intel Core i7-10700",
        "AMD Ryzen 5 5600G"]

DEMO_USERS = [
    # username, имя, фамилия, роль, коды организаций
    ("viewer", "Ольга", "Смотрова", "inventory_viewer", ["400"]),
    ("storekeeper", "Павел", "Складов", "inventory_storekeeper", ["400", "401"]),
    ("manager", "Ирина", "Управова", "inventory_admin", ["400", "401", "402", "403"]),
]


class Command(BaseCommand):
    help = "Заполняет БД тестовыми данными (организации, сотрудники, оборудование, события, акты)"

    def add_arguments(self, parser):
        parser.add_argument("--equipment", type=int, default=80, help="Сколько единиц оборудования создать")
        parser.add_argument("--seed", type=int, default=42, help="Seed генератора случайных чисел")

    @transaction.atomic
    def handle(self, *args, **options):
        rnd = random.Random(options["seed"])

        orgs = self._organizations()
        departments = self._departments(orgs)
        employees = self._employees(rnd, departments)
        types = self._equipment_types()
        groups = bootstrap_roles()
        users = self._users(groups, orgs)
        equipment = self._equipment(rnd, options["equipment"], orgs, types, employees, users)
        events = self._events(rnd, equipment, employees, users)
        docs = self._documents(rnd, orgs, employees, users)

        self.stdout.write(self.style.SUCCESS(
            f"Готово: организаций {len(orgs)}, подразделений {len(departments)}, сотрудников {len(employees)}, "
            f"типов {len(types)}, оборудования +{len(equipment)}, событий +{events}, актов +{docs}, "
            f"пользователей {len(users)} (пароль: {DEMO_PASSWORD})"
        ))

    def _organizations(self):
        orgs = {}
        for code, name in ORGANIZATIONS:
            org, _ = Organization.objects.get_or_create(code=code, defaults={"name": name})
            orgs[code] = org
        return orgs

    def _departments(self, orgs):
        result = []
        for org in orgs.values():
            for name in DEPARTMENTS:
                dep, _ = Department.objects.get_or_create(organization=org, name=name)
                result.append(dep)
        return result

    def _employees(self, rnd, departments):
        result = []
        for dep in departments:
            existing = list(Employee.objects.filter(department=dep))
            result += existing
            for _ in range(max(0, 4 - len(existing))):
                last = rnd.choice(LAST_NAMES)
                if rnd.random() < 0.5:
                    full_name = f"{last} {rnd.choice(FIRST_NAMES)[0]} {rnd.choice(MALE_PATRONYMIC)}"
                else:
                    full_name = f"{last}а {rnd.choice(FEMALE_FIRST)} {rnd.choice(FIRST_NAMES)[1]}"
                result.append(Employee.objects.create(
                    organization=dep.organization,
                    department=dep,
                    full_name=full_name,
                    email=f"user{rnd.randint(1000, 9999)}@example.test",
                    phone=f"+375 29 {rnd.randint(100, 999)}-{rnd.randint(10, 99)}-{rnd.randint(10, 99)}",
                    active=rnd.random() > 0.1,
                ))
        return result

    def _equipment_types(self):
        types = {}
        for name, category in EQUIPMENT_TYPES:
            et, _ = EquipmentType.objects.get_or_create(name=name, defaults={"category": category})
            types[name] = et
        return types

    def _users(self, groups, orgs):
        users = []
        for username, first, last, role, org_codes in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username, defaults={"first_name": first, "last_name": last})
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            user.groups.set([groups[role]])
            access, _ = UserOrganizationAccess.objects.get_or_create(user=user)
            access.organizations.set([orgs[c] for c in org_codes])
            users.append(user)
        return users

    def _equipment(self, rnd, count, orgs, types, employees, users):
        statuses = ([EquipmentStatus.IN_USE] * 12 + [EquipmentStatus.RESERVE] * 3 +
                    [EquipmentStatus.REPAIR, EquipmentStatus.TO_TRANSFER,
                     EquipmentStatus.TO_WRITE_OFF, EquipmentStatus.WRITTEN_OFF])
        by_org = {}
        for emp in employees:
            if emp.active:
                by_org.setdefault(emp.organization_id, []).append(emp)

        start_no = Equipment.objects.count() + 1
        result = []
        for i in range(count):
            org = rnd.choice(list(orgs.values()))
            type_name = rnd.choice(list(types))
            et = types[type_name]
            model = rnd.choice(MODELS[type_name])
            status = rnd.choice(statuses)
            assigned = rnd.choice(by_org[org.id]) if status == EquipmentStatus.IN_USE and org.id in by_org else None
            no = start_no + i

            eq = Equipment(
                organization=org,
                equipment_type=et,
                name=f"{type_name} {model.split()[0]} {org.code}-{no:03d}",
                inventory_number=f"{org.code}-{10000 + no}",
                serial_number=f"SN{rnd.randint(10 ** 7, 10 ** 8 - 1)}",
                model=model,
                commissioning_date=date.today() - timedelta(days=rnd.randint(30, 365 * 8)),
                status=status,
                assigned_to=assigned,
                created_by=rnd.choice(users),
            )
            if et.category == EquipmentType.Category.COMPUTER:
                eq.cpu = rnd.choice(CPUS)
                eq.ram_gb = rnd.choice([4, 8, 8, 16, 16, 32])
                if rnd.random() < 0.4:
                    eq.storageHDD_gb = rnd.choice([500, 1000])
                eq.storageSDD_gb = rnd.choice([128, 256, 512])
                eq.specs = f"{eq.cpu}, {eq.ram_gb} ГБ ОЗУ"
            elif et.category == EquipmentType.Category.PRINT:
                eq.print_format = rnd.choice(["A4", "A4", "A3"])
                eq.print_mode = rnd.choice([PrintMode.MONO, PrintMode.MONO, PrintMode.COLOR])
            eq.updated_by = eq.created_by
            eq.save()
            result.append(eq)
        return result

    def _events(self, rnd, equipment, employees, users):
        count = 0
        now = timezone.now()
        for eq in equipment:
            created_at = now - timedelta(days=rnd.randint(1, 600))
            if eq.assigned_to:
                EquipmentEvent.objects.create(
                    equipment=eq, event_type=EquipmentEventType.ASSIGN, created_at=created_at,
                    created_by=rnd.choice(users), to_employee=eq.assigned_to, comment="Первичное закрепление")
                count += 1
            if eq.status != EquipmentStatus.IN_USE:
                EquipmentEvent.objects.create(
                    equipment=eq, event_type=EquipmentEventType.STATUS,
                    created_at=created_at + timedelta(days=rnd.randint(1, 30)), created_by=rnd.choice(users),
                    old_status=EquipmentStatus.IN_USE, new_status=eq.status, comment="Смена статуса")
                count += 1
            if rnd.random() < 0.2:
                same_org = [e for e in employees if e.organization_id == eq.organization_id]
                EquipmentEvent.objects.create(
                    equipment=eq, event_type=EquipmentEventType.MOVE,
                    created_at=created_at - timedelta(days=rnd.randint(30, 300)), created_by=rnd.choice(users),
                    from_employee=rnd.choice(same_org), to_employee=eq.assigned_to,
                    document_number=f"ПМ-{rnd.randint(1, 999)}", comment="Перемещение между сотрудниками")
                count += 1
        return count

    def _documents(self, rnd, orgs, employees, users):
        created = 0
        for org in orgs.values():
            org_emps = [e for e in employees if e.organization_id == org.id and e.active]
            writeoff_eq = list(Equipment.objects.filter(organization=org, status=EquipmentStatus.WRITTEN_OFF)[:3])
            transfer_eq = list(Equipment.objects.filter(organization=org, status=EquipmentStatus.IN_USE)[:2])

            plans = [(DocumentType.WRITE_OFF, f"СП-{org.code}-1", writeoff_eq, None),
                     (DocumentType.TRANSFER, f"АП-{org.code}-1", transfer_eq, rnd.choice(org_emps))]
            for doc_type, number, items, to_emp in plans:
                if not items:
                    continue
                doc, is_new = InventoryDocument.objects.get_or_create(
                    doc_type=doc_type, organization=org, number=number,
                    defaults={
                        "date": date.today() - timedelta(days=rnd.randint(1, 90)),
                        "to_employee": to_emp,
                        "created_by": rnd.choice(users),
                        "comment": "Тестовый акт",
                        "applied_at": timezone.now(),
                    })
                if is_new:
                    for eq in items:
                        InventoryDocumentLine.objects.create(document=doc, equipment=eq)
                    created += 1
        return created
