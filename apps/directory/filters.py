import django_filters
from django import forms
from django.db import models
from .filters_mixins import BootstrapFilterFormMixin
from .models import Organization, Department, Employee


class EmployeeFilter(BootstrapFilterFormMixin, django_filters.FilterSet):
    q = django_filters.CharFilter(method="search",
                                  label="Поиск",
                                  widget=forms.TextInput(attrs={"placeholder": "ФИО, e-mail, Телефон..."}))
    organization = django_filters.ModelChoiceFilter(queryset=Organization.objects.all(), label="Организация")
    department = django_filters.ModelChoiceFilter(queryset=Department.objects.select_related("organization").all(),
                                                  label="Подразделение")
    show_inactive = django_filters.BooleanFilter(
        method="filter_show_inactive",
        label="Показывать неактивных",
        widget=forms.CheckboxInput(),
    )

    class Meta:
        model = Employee
        fields = ["organization", "department"]

    def filter_show_inactive(self, queryset, name, value):
        return queryset if value else queryset.filter(active=True)

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
    show_inactive = django_filters.BooleanFilter(
        method="filter_show_inactive",
        label="Показывать неактивные",
        widget=forms.CheckboxInput(),
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

    def filter_show_inactive(self, queryset, name, value):
        # value=True => показать все
        if value:
            return queryset
        # по умолчанию (нет галки) — только активные
        return queryset.filter(active=True)

class DepartmentFilter(BootstrapFilterFormMixin, django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="search",
        label="Поиск",
        widget=forms.TextInput(attrs={"placeholder": "Подразделение или организация..."})
    )
    organization = django_filters.ModelChoiceFilter(
        queryset=Organization.objects.all(),
        label="Организация"
    )
    show_inactive = django_filters.BooleanFilter(
        method="filter_show_inactive",
        label="Показывать неактивные",
        widget=forms.CheckboxInput(),
    )

    class Meta:
        model = Department
        fields = ["organization"]

    def filter_show_inactive(self, queryset, name, value):
        return queryset if value else queryset.filter(active=True)

    def search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            models.Q(name__icontains=value)
            | models.Q(organization__name__icontains=value)
            | models.Q(organization__code__icontains=value)
        )
