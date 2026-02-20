import django_filters
from .models import Equipment, Employee, EquipmentStatus, EquipmentType, Organization, Department


class EquipmentFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label="Поиск")
    status = django_filters.ChoiceFilter(choices=EquipmentStatus.choices, label="Статус")
    equipment_type = django_filters.ModelChoiceFilter(queryset=EquipmentType.objects.all(), label="Тип")
    organization = django_filters.ModelChoiceFilter(queryset=Organization.objects.all(), label="Организация")
    assigned_to = django_filters.ModelChoiceFilter(queryset=Employee.objects.all(), label="Сотрудник")
    commissioning_date__gte = django_filters.DateFilter(field_name="commissioning_date", lookup_expr="gte", label="Ввод с")
    commissioning_date__lte = django_filters.DateFilter(field_name="commissioning_date", lookup_expr="lte", label="Ввод по")

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


class EmployeeFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label="Поиск")
    organization = django_filters.ModelChoiceFilter(queryset=Organization.objects.all(), label="Организация")
    department = django_filters.ModelChoiceFilter(queryset=Department.objects.select_related("organization").all(), label="Подразделение")
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
