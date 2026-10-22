from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryDocument, DocumentType, EquipmentStatus, EquipmentEvent, EquipmentEventType


def change_equipment(eq, user, *, to_employee=..., new_status=None, event_type=EquipmentEventType.MOVE,
                     document_number="", comment=""):
    """
    Единая точка изменения закрепления/статуса оборудования.
    Всегда фиксирует автора: equipment.updated_by и EquipmentEvent.created_by.

    to_employee: новый сотрудник (None — снять закрепление, ... — не менять).
    new_status: новый статус (None — не менять).
    Возвращает созданное событие или None, если ничего не изменилось.
    """
    from_emp = eq.assigned_to
    old_status = eq.status

    assigned_changed = to_employee is not ... and getattr(to_employee, "pk", None) != eq.assigned_to_id
    status_changed = new_status is not None and new_status != old_status
    if not assigned_changed and not status_changed:
        return None

    with transaction.atomic():
        if assigned_changed:
            eq.assigned_to = to_employee
        if status_changed:
            eq.status = new_status
        eq.updated_by = user
        eq.save()

        return EquipmentEvent.objects.create(
            equipment=eq,
            event_type=event_type,
            created_by=user,
            from_employee=from_emp if assigned_changed else None,
            to_employee=eq.assigned_to if assigned_changed else None,
            old_status=old_status if status_changed else "",
            new_status=eq.status if status_changed else "",
            document_number=document_number,
            comment=comment,
        )


def log_equipment_edit(eq, user, *, old_assigned_id, old_status, comment=""):
    """
    Для мест, где оборудование сохраняется целиком (форма редактирования, импорт CSV):
    если сменился сотрудник или статус — пишет событие в историю с автором.
    """
    assigned_changed = old_assigned_id != eq.assigned_to_id
    status_changed = old_status != eq.status
    if not assigned_changed and not status_changed:
        return None
    return EquipmentEvent.objects.create(
        equipment=eq,
        event_type=EquipmentEventType.MOVE if assigned_changed else EquipmentEventType.STATUS,
        created_by=user,
        from_employee_id=old_assigned_id if assigned_changed else None,
        to_employee_id=eq.assigned_to_id if assigned_changed else None,
        old_status=old_status if status_changed else "",
        new_status=eq.status if status_changed else "",
        comment=comment,
    )


def log_note_change(eq, user, old_note):
    """Если примечание изменилось — событие «примечание» в истории с автором."""
    if (old_note or "") == (eq.note or ""):
        return None
    return EquipmentEvent.objects.create(
        equipment=eq,
        event_type=EquipmentEventType.NOTE,
        created_by=user,
        comment=eq.note or "Примечание удалено",
    )


def change_equipment_note(eq, user, note):
    """Изменить только примечание (быстрое редактирование из списка)."""
    note = (note or "").strip()
    old_note = eq.note
    if note == (old_note or ""):
        return None
    with transaction.atomic():
        eq.note = note
        eq.updated_by = user
        eq.save(update_fields=["note", "updated_by", "updated_at"])
        return log_note_change(eq, user, old_note)


def apply_document(doc: InventoryDocument, user=None):
    """
    Применяет документ к оборудованию:
      - TRANSFER: assigned_to = doc.to_employee
      - WRITE_OFF: status = WRITTEN_OFF и снимаем закрепление
    Создает EquipmentEvent на каждую строку (автор — user).
    """
    if doc.applied_at:
        return  # уже применен

    with transaction.atomic():
        for line in doc.lines.select_related("equipment", "equipment__assigned_to"):
            eq = line.equipment

            if doc.doc_type == DocumentType.TRANSFER:
                change_equipment(
                    eq, user,
                    to_employee=doc.to_employee,
                    new_status=EquipmentStatus.IN_USE,
                    event_type=EquipmentEventType.ASSIGN,
                    document_number=doc.number,
                    comment="Передача по акту",
                )

            elif doc.doc_type == DocumentType.WRITE_OFF:
                change_equipment(
                    eq, user,
                    to_employee=None,
                    new_status=EquipmentStatus.WRITTEN_OFF,
                    event_type=EquipmentEventType.WRITE_OFF,
                    document_number=doc.number,
                    comment="Списано по акту",
                )

        doc.applied_at = timezone.now()
        doc.save(update_fields=["applied_at"])
