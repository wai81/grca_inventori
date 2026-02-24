from django.db import models
from django.utils import timezone

from config import settings



class EquipmentType(models.Model):
    name = models.CharField(max_length=120, unique=True)  # ПК, Принтер, МФУ, Монитор, Сканер, ИБП...

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

class Equipment(models.Model):
    organization = models.ForeignKey("directory.Organization", on_delete=models.PROTECT, related_name="equipment", verbose_name="Организация")
    equipment_type = models.ForeignKey(EquipmentType, on_delete=models.PROTECT, related_name="equipment", verbose_name="Тип оборудования")

    name = models.CharField(max_length=200, verbose_name="Наименование")  # коротко: "ПК Lenovo", "Принтер HP"
    inventory_number = models.CharField(max_length=100, blank=True, verbose_name="Инв. №")  # если есть
    pc_number = models.CharField(max_length=50, blank=True, verbose_name="Номер ПК")  # если есть: PC400-001

    serial_number = models.CharField(max_length=120, blank=True, verbose_name="Серийный №")
    model = models.CharField(max_length=120, blank=True, verbose_name="Модель")

    specs = models.TextField(blank=True, verbose_name="Характеристики")  # характеристики в свободном виде (или позже вынести в JSON)
    commissioning_date = models.DateField(null=True, blank=True, verbose_name="Дата поступления")
    status = models.CharField(max_length=20, choices=EquipmentStatus.choices, default=EquipmentStatus.IN_USE, verbose_name="Статус")

    assigned_to = models.ForeignKey(
        "directory.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_equipment",
        verbose_name="Закреплен"
    )

    # Уникальный токен для QR (удобно печатать/сканировать и открывать карточку)
    qr_token = models.CharField(max_length=32, unique=True, editable=False)

    created_at = models.DateTimeField(default=timezone.now,verbose_name="Создан")

    class Meta:
        verbose_name = "Оборудование"
        verbose_name_plural = "Оборудование"
        indexes = [
            models.Index(fields=["inventory_number"]),
            models.Index(fields=["pc_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["organization", "equipment_type"]),
        ]

    def __str__(self):
        inv = f" (инв. {self.inventory_number})" if self.inventory_number else ""
        return f"{self.name}{inv}"

    def save(self, *args, **kwargs):
        if not self.qr_token:
            # простой уникальный токен
            import secrets
            self.qr_token = secrets.token_hex(16)
        super().save(*args, **kwargs)

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

    from_employee = models.ForeignKey("directory.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="docs_from")
    to_employee = models.ForeignKey("directory.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="docs_to")

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
    pc_number_snapshot = models.CharField(max_length=50, blank=True)
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
        if not self.pc_number_snapshot:
            self.pc_number_snapshot = self.equipment.pc_number or ""
        super().save(*args, **kwargs)