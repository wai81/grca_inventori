from dateutil.relativedelta import relativedelta
from django.db import models
from django.utils import timezone

from apps.directory.models import Employee, Organization
from config import settings


class EquipmentType(models.Model):
    class Category(models.TextChoices):
        COMPUTER = "computer", "Компьютер"
        PRINT = "print", "Печать"
        OTHER = "other", "Другое"

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)

    class Meta:
        verbose_name = "Тип оборудования"
        verbose_name_plural = "Типы оборудования"

    def __str__(self):
        return self.name


class EquipmentStatus(models.TextChoices):
    RESERVE = "reserve", "резерв"
    REPAIR = "repair", "в ремонте"
    IN_USE = "in_use", "используется"
    TO_TRANSFER = "to_transfer", "на передачу"
    TO_WRITE_OFF = "to_write_off", "на списание"
    WRITTEN_OFF = "written_off", "списано"


# Принтеры/МФУ
class PrintMode(models.TextChoices):
    MONO = "mono", "Монохромная"
    COLOR = "color", "Цветная"


class Equipment(models.Model):
    organization = models.ForeignKey("directory.Organization", on_delete=models.PROTECT, related_name="equipment",
                                     verbose_name="Организация")
    equipment_type = models.ForeignKey(EquipmentType, on_delete=models.PROTECT, related_name="equipment",
                                       verbose_name="Тип оборудования")

    name = models.CharField(max_length=200,
                            verbose_name="Наименование")  # коротко: : PC400-001 "ПК Lenovo", "Принтер HP"
    inventory_number = models.CharField(max_length=100, blank=True, verbose_name="Инв. №")  # если есть
    # pc_number = models.CharField(max_length=50, blank=True, verbose_name="Номер ПК")  # если есть: PC400-001

    serial_number = models.CharField(max_length=120, blank=True, verbose_name="Серийный №")
    model = models.CharField(max_length=120, blank=True, verbose_name="Модель")

    specs = models.TextField(blank=True,
                             verbose_name="Характеристики")  # характеристики в свободном виде (или позже вынести в JSON)
    commissioning_date = models.DateField(null=True, blank=True, verbose_name="Дата поступления")
    status = models.CharField(max_length=20, choices=EquipmentStatus.choices, default=EquipmentStatus.IN_USE,
                              verbose_name="Статус")

    assigned_to = models.ForeignKey(
        "directory.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_equipment",
        verbose_name="Закреплен"
    )

    # Уникальный токен для QR (удобно печатать/сканировать и открывать карточку)
    qr_token = models.CharField(max_length=32, unique=True, editable=False)

    # Компьютеры
    cpu = models.CharField("Процессор", max_length=255, blank=True)
    ram_gb = models.PositiveSmallIntegerField("ОЗУ (ГБ)", null=True, blank=True)
    storageHDD_gb = models.PositiveIntegerField(verbose_name="HDD, Гб", null=True, blank=True)
    storageSDD_gb = models.PositiveIntegerField(verbose_name="SDD, Гб", null=True, blank=True)

    print_format = models.CharField("Формат печати", max_length=50, blank=True)  # например: A4/A3
    print_mode = models.CharField("Печать", max_length=10, choices=PrintMode.choices, blank=True)

    created_at = models.DateTimeField(default=timezone.now, verbose_name="Создан")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="equipment_created",
        verbose_name="Создал",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="equipment_updated",
        verbose_name="Изменил",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлён",
    )

    class Meta:
        verbose_name = "Оборудование"
        verbose_name_plural = "Оборудование"
        indexes = [
            models.Index(fields=["inventory_number"]),
            # models.Index(fields=["pc_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["qr_token"]),
            models.Index(fields=["organization", "equipment_type"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        inv = f" (инв. {self.inventory_number})" if self.inventory_number else ""
        return f"{self.name}{inv}"

    def save(self, *args, **kwargs):
        if not self.qr_token:
            # простой уникальный токен
            import secrets
            self.qr_token = secrets.token_hex(16)
        super().save(*args, **kwargs)

    @property
    def usage_duration(self):
        """Возвращает срок использования как relativedelta или None."""
        if not self.commissioning_date:
            return None
        today = timezone.now().date()
        if self.commissioning_date > today:
            return None
        return relativedelta(today, self.commissioning_date)

    @property
    def usage_duration_display(self):
        """Срок использования в формате '2 г. 3 мес.' """
        rd = self.usage_duration
        if rd is None:
            return "—"

        parts = []
        if rd.years:
            y = rd.years
            if y % 10 == 1 and y % 100 != 11:
                parts.append(f"{y} год")
            elif 2 <= y % 10 <= 4 and not (12 <= y % 100 <= 14):
                parts.append(f"{y} года")
            else:
                parts.append(f"{y} лет")

        if rd.months:
            m = rd.months
            if m % 10 == 1 and m % 100 != 11:
                parts.append(f"{m} месяц")
            elif 2 <= m % 10 <= 4 and not (12 <= m % 100 <= 14):
                parts.append(f"{m} месяца")
            else:
                parts.append(f"{m} месяцев")

        if not parts:
            if rd.days:
                d = rd.days
                if d % 10 == 1 and d % 100 != 11:
                    parts.append(f"{d} день")
                elif 2 <= d % 10 <= 4 and not (12 <= d % 100 <= 14):
                    parts.append(f"{d} дня")
                else:
                    parts.append(f"{d} дней")
            else:
                return "менее дня"

        return " ".join(parts)


class EquipmentEventType(models.TextChoices):
    ASSIGN = "assign", "закрепление"
    MOVE = "move", "перемещение"
    REPAIR = "repair", "ремонт"
    STATUS = "status", "смена статуса"
    WRITE_OFF = "write_off", "списание"
    NOTE = "note", "примечание"


class EquipmentEvent(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EquipmentEventType.choices)
    created_at = models.DateTimeField(default=timezone.now)
    # кто создал событие
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Создал",
        related_name="equipment_events",
    )
    from_employee = models.ForeignKey(
        "directory.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="events_from"
    )
    to_employee = models.ForeignKey(
        "directory.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="events_to"
    )

    old_status = models.CharField(max_length=20, choices=EquipmentStatus.choices, blank=True)
    new_status = models.CharField(max_length=20, choices=EquipmentStatus.choices, blank=True)

    document_number = models.CharField(max_length=120, blank=True)  # акт/накладная/заявка
    comment = models.TextField(blank=True)

    class Meta:
        verbose_name = "Событие оборудования"
        verbose_name_plural = "События оборудования"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.equipment} — {self.get_event_type_display()} — {self.created_at:%Y-%m-%d}"


class DocumentType(models.TextChoices):
    TRANSFER = "transfer", "акт передачи"
    WRITE_OFF = "write_off", "акт списания"


class InventoryDocument(models.Model):
    """
    Документ (акт), который может содержать несколько единиц оборудования.
    """
    doc_type = models.CharField(max_length=20, choices=DocumentType.choices)
    organization = models.ForeignKey("directory.Organization", on_delete=models.PROTECT, related_name="documents")

    number = models.CharField(max_length=60)  # номер акта/документа
    date = models.DateField(default=timezone.now)

    from_employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="docs_from")
    to_employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="docs_to")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    comment = models.TextField(blank=True)

    applied_at = models.DateTimeField(null=True, blank=True)  # когда применили (обновили статусы/закрепления)

    class Meta:
        unique_together = [("doc_type", "organization", "number")]

    def __str__(self):
        return f"{self.get_doc_type_display()} №{self.number} от {self.date:%Y-%m-%d}"


class InventoryDocumentLine(models.Model):
    document = models.ForeignKey(InventoryDocument, on_delete=models.CASCADE, related_name="lines")
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT)

    # снимок на момент формирования (для печати)
    inventory_number_snapshot = models.CharField(max_length=100, blank=True)
    # pc_number_snapshot = models.CharField(max_length=50, blank=True)
    name_snapshot = models.CharField(max_length=200)
    type_snapshot = models.CharField(max_length=120, blank=True)

    class Meta:
        unique_together = [("document", "equipment")]

    def save(self, *args, **kwargs):
        if not self.name_snapshot:
            self.name_snapshot = self.equipment.name
        if not self.type_snapshot:
            self.type_snapshot = str(self.equipment.equipment_type)
        if not self.inventory_number_snapshot:
            self.inventory_number_snapshot = self.equipment.inventory_number or ""
        # if not self.pc_number_snapshot:
        #     self.pc_number_snapshot = self.equipment.pc_number or ""
        super().save(*args, **kwargs)
