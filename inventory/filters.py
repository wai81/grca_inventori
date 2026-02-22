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
        )


