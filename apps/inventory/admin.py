from django.contrib import admin, messages
from apps.inventory.models import Equipment
from apps.inventory.services import log_equipment_edit


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "inventory_number", "organization", "equipment_type")
    readonly_fields = ("created_by", "created_at", "updated_by", "updated_at")

    def save_model(self, request, obj, form, change):
        old = None
        if change:
            old = Equipment.objects.values("assigned_to_id", "status").get(pk=obj.pk)
        else:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        if old:
            log_equipment_edit(obj, request.user, old_assigned_id=old["assigned_to_id"], old_status=old["status"],
                               comment="Изменено в админке")
