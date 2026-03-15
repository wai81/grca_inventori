from django.contrib import admin, messages
from apps.inventory.models import Equipment



@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "inventory_number", "organization", "equipment_type")

