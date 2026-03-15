
from django import forms
from django.db.models import Q
from apps.directory.models import Employee, Organization
from apps.inventory.models import Equipment, EquipmentStatus, EquipmentType
from apps.directory.access import get_allowed_organizations


class EquipmentForm(forms.ModelForm):

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        allowed_orgs = Organization.objects.none()
        if user:
            allowed_orgs = get_allowed_organizations(user)

        if not user or not user.is_superuser:
            self.fields["organization"].queryset = allowed_orgs.order_by("code", "name")

        # ── определяем org_id ──
        org_id = None
        if self.data.get("organization"):
            org_id = self.data.get("organization")
        elif self.instance.pk and self.instance.organization_id:
            org_id = self.instance.organization_id
        elif self.initial.get("organization"):
            org_id = self.initial.get("organization")

        # ── текущий assigned_to (для редактирования) ──
        current_assigned_id = self.instance.assigned_to_id if self.instance.pk else None

        # ── queryset сотрудников ──
        if org_id:
            emp_qs = Employee.objects.filter(organization_id=org_id)

            # включаем текущего сотрудника, даже если он неактивный
            if current_assigned_id:
                emp_qs = emp_qs.filter(Q(active=True) | Q(pk=current_assigned_id))
            else:
                emp_qs = emp_qs.filter(active=True)
        else:
            emp_qs = Employee.objects.none()

        if user and not user.is_superuser:
            emp_qs = emp_qs.filter(organization__in=allowed_orgs)

        self.fields["assigned_to"].queryset = emp_qs.select_related("department").order_by("full_name")
        self.fields["assigned_to"].required = False
        self.fields["assigned_to"].empty_label = (
            "— не закреплять —" if org_id else "— сначала выберите организацию —"
        )

        for _, field in self.fields.items():
            if getattr(field.widget, "input_type", "") == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned = super().clean()

        org = cleaned.get("organization")
        as_to = cleaned.get("assigned_to")
        if org and as_to and as_to.organization_id != org.id:
            self.add_error("assigned_to", "Сотрудник не принадлежит выбранной организации")

        et = cleaned.get("equipment_type")
        cat = getattr(et, "category", None)

        if cat == "computer":
            if not cleaned.get("cpu"):
                self.add_error("cpu", "Укажите процессор.")
            if not cleaned.get("ram_gb"):
                self.add_error("ram_gb", "Укажите объём ОЗУ.")
            if not (cleaned.get("storageHDD_gb") or cleaned.get("storageSDD_gb")):
                self.add_error("storageHDD_gb", "Укажите объём HDD или SSD.")
                self.add_error("storageSDD_gb", "Укажите объём HDD или SSD.")
            cleaned["print_format"] = ""
            cleaned["print_mode"] = ""

        elif cat == "print":
            if not cleaned.get("print_format"):
                self.add_error("print_format", "Укажите формат печати.")
            if not cleaned.get("print_mode"):
                self.add_error("print_mode", "Укажите тип печати.")
            cleaned["cpu"] = ""
            cleaned["ram_gb"] = None
            cleaned["storageHDD_gb"] = None
            cleaned["storageSDD_gb"] = None

        return cleaned

    class Meta:
        model = Equipment
        fields = [
            "organization", "equipment_type", "name", "model",
            "inventory_number", "serial_number",
            "cpu", "ram_gb", "storageSDD_gb", "storageHDD_gb", "print_format", "print_mode",
            "specs", "commissioning_date", "status", "assigned_to",
        ]
        widgets = {
            "commissioning_date": forms.DateInput(attrs={"type": "date"}),
            "specs": forms.Textarea(attrs={"rows": 4}),
        }


class EquipmentMoveForm(forms.Form):
    to_employee = forms.ModelChoiceField(
        label="Кому передать (сотрудник)",
        queryset=Employee.objects.filter(active=True).select_related("organization", "department").order_by(
            "organization__code", "department__name", "full_name"
        ),
        required=False,
        empty_label="— снять закрепление —",
    )

    new_status = forms.ChoiceField(
        label="Новый статус",
        choices=EquipmentStatus.choices,
        required=True,
        initial=EquipmentStatus.IN_USE,
    )
    document_number = forms.CharField(label="Номер документа", required=False)
    comment = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, equipment=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.equipment = equipment
        self.user = user

        qs = Employee.objects.filter(active=True)

        if equipment and equipment.organization_id:
            qs = qs.filter(organization=equipment.organization)

        if user and not user.is_superuser:
            qs = qs.filter(organization__in=get_allowed_organizations(user))

        self.fields["to_employee"].queryset = qs.select_related("department").order_by("full_name")

        if self.equipment:
            self.fields["new_status"].initial = self.equipment.status
            self.fields["to_employee"].initial = self.equipment.assigned_to_id

        for _, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"

    def clean_to_employee(self):
        emp = self.cleaned_data.get("to_employee")

        if emp and self.equipment and emp.organization_id != self.equipment.organization_id:
            raise forms.ValidationError("Нельзя передать оборудование сотруднику другой организации.")

        return emp


class EquipmentTypeForm(forms.ModelForm):
    class Meta:
        model = EquipmentType
        fields = ["name", "category"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class EquipmentCSVImportForm(forms.Form):
    csv_file = forms.FileField(label="CSV файл")
    update_existing = forms.BooleanField(
        label="Обновлять существующие записи по инвентарному номеру",
        required=False,
        initial=True,
    )
