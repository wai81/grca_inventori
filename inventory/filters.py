import django_filters
from django import forms
from django.db import models
from directory.models import Organization, Employee
from .filters_mixins import BootstrapFilterFormMixin
from .models import Equipment,  EquipmentStatus, EquipmentType


class EquipmentFilter(BootstrapFilterFormMixin, django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="search",
        label="Поиск",
        widget=forms.TextInput(attrs={"placeholder": "Название, инв. №, серийный, модель..."})
    )

    status = django_filters.ChoiceFilter(choices=EquipmentStatus.choices, label="Статус")
    equipment_type = django_filters.ModelChoiceFilter(queryset=EquipmentType.objects.all(), label="Тип")
    organization = django_filters.ModelChoiceFilter(queryset=Organization.objects.all(), label="Организация")
    assigned_to = django_filters.ModelChoiceFilter(queryset=Employee.objects.all(), label="Сотрудник")

    commissioning_date__gte = django_filters.DateFilter(
        field_name="commissioning_date", lookup_expr="gte", label="Ввод с",
        widget=forms.DateInput(attrs={"type": "date"})
    )
    commissioning_date__lte = django_filters.DateFilter(
        field_name="commissioning_date", lookup_expr="lte", label="Ввод по",
        widget=forms.DateInput(attrs={"type": "date"})
    )

    # --- Компьютер ---
    cpu = django_filters.CharFilter(
        field_name="cpu", lookup_expr="icontains", label="CPU содержит",
        widget=forms.TextInput(attrs={"placeholder": "i5, Ryzen..."})
    )
    ram_gb__gte = django_filters.NumberFilter(field_name="ram_gb", lookup_expr="gte", label="ОЗУ от (ГБ)")
    ram_gb__lte = django_filters.NumberFilter(field_name="ram_gb", lookup_expr="lte", label="ОЗУ до (ГБ)")

    storageHDD_gb__gte = django_filters.NumberFilter(field_name="storageHDD_gb", lookup_expr="gte", label="HDD от (ГБ)")
    storageHDD_gb__lte = django_filters.NumberFilter(field_name="storageHDD_gb", lookup_expr="lte", label="HDD до (ГБ)")

    storageSDD_gb__gte = django_filters.NumberFilter(field_name="storageSDD_gb", lookup_expr="gte", label="SSD от (ГБ)")
    storageSDD_gb__lte = django_filters.NumberFilter(field_name="storageSDD_gb", lookup_expr="lte", label="SSD до (ГБ)")

    # --- Печать ---
    print_format = django_filters.CharFilter(
        field_name="print_format", lookup_expr="icontains", label="Формат печати",
        widget=forms.TextInput(attrs={"placeholder": "A4, A3..."})
    )
    print_mode = django_filters.ChoiceFilter(
        field_name="print_mode", choices=Equipment.PrintMode.choices, label="Печать"
    )

    class Meta:
        model = Equipment
        fields = [
            "organization",
            "equipment_type",
            "status",
            "assigned_to",
        ]

    def search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            models.Q(name__icontains=value)
            | models.Q(inventory_number__icontains=value)
            | models.Q(pc_number__icontains=value)
            | models.Q(serial_number__icontains=value)
            | models.Q(model__icontains=value)
            | models.Q(specs__icontains=value)
            | models.Q(cpu__icontains=value)
            | models.Q(print_format__icontains=value)
        )


