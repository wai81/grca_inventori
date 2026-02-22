import django_filters
from django import forms

from .filters_mixins import BootstrapFilterFormMixin
from .models import Organization, Department, Employee


class EmployeeFilter(BootstrapFilterFormMixin, django_filters.FilterSet):
    q = django_filters.CharFilter(method="search",
                                  label="Поиск",
                                  widget=forms.TextInput(attrs={"placeholder": "ФИО, e-mail, Телефон..."}))
    organization = django_filters.ModelChoiceFilter(queryset=Organization.objects.all(), label="Организация")
    department = django_filters.ModelChoiceFilter(queryset=Department.objects.select_related("organization").all(),
                                                  label="Подразделение")
    active = django_filters.BooleanFilter(label="Активен")

    class Meta:
        model = Employee
        fields = ["organization", "department", "active"]

    def search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            models.Q(full_name__icontains=value)
            | models.Q(email__icontains=value)
            | models.Q(phone__icontains=value)
        )


class OrganizationFilter(BootstrapFilterFormMixin, django_filters.FilterSet):

    q = django_filters.CharFilter(
        method="search",
        label="Поиск",
        widget=forms.TextInput(attrs={"placeholder": "Код или название..."})
    )


    class Meta:
        model = Organization
        fields = []

    def search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            models.Q(code__icontains=value) |
            models.Q(name__icontains=value)
        )
