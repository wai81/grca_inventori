from django.db import transaction
from django.utils import timezone

from inventory.models import InventoryDocument, DocumentType, EquipmentStatus, EquipmentEvent, EquipmentEventType


def apply_document(doc: InventoryDocument):
    """
    Применяет документ к оборудованию:
      - TRANSFER: assigned_to = doc.to_employee
      - WRITE_OFF: status = WRITTEN_OFF и снимаем закрепление
    Создает EquipmentEvent на каждую строку.
    """
    if doc.applied_at:
        return  # уже применен

    with transaction.atomic():
        for line in doc.lines.select_related("equipment"):
            eq = line.equipment

            if doc.doc_type == DocumentType.TRANSFER:
                from_emp = eq.assigned_to
                eq.assigned_to = doc.to_employee
                eq.status = EquipmentStatus.IN_USE
                eq.save()

                EquipmentEvent.objects.create(
                    equipment=eq,
                    event_type=EquipmentEventType.ASSIGN,
                    from_employee=from_emp,
                    to_employee=doc.to_employee,
                    document_number=doc.number,
                    comment="Передача по акту",
                )

            elif doc.doc_type == DocumentType.WRITE_OFF:
                old = eq.status
                from_emp = eq.assigned_to
                eq.assigned_to = None
                eq.status = EquipmentStatus.WRITTEN_OFF
                eq.save()

                EquipmentEvent.objects.create(
                    equipment=eq,
                    event_type=EquipmentEventType.WRITE_OFF,
                    from_employee=from_emp,
                    old_status=old,
                    new_status=EquipmentStatus.WRITTEN_OFF,
                    document_number=doc.number,
                    comment="Списано по акту",
                )

        doc.applied_at = timezone.now()
        doc.save(update_fields=["applied_at"])