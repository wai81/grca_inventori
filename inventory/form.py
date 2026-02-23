from django import forms
from directory.models import Employee
from inventory.models import Equipment, EquipmentStatus


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            "organization",
            "equipment_type",
            "name",
            "inventory_number",
            "pc_number",
            "serial_number",
            "model",
            "specs",
            "commissioning_date",
            "status",
            "assigned_to",
        ]

    widgets = {
        "commissioning_date": forms.DateInput(attrs={"type": "date"}),
        "specs": forms.Textarea(attrs={"rows": 4}),
    }

    def init(self, *args, **kwargs):
        super().init(*args, **kwargs)

        self.fields["assigned_to"].queryset = Employee.objects.filter(active=True).select_related("organization",
                                                                                                  "department").order_by(
            "organization__code", "department__name", "full_name"
        )
        self.fields["assigned_to"].required = False

        for _, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


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

    def __init__(self, *args, **kwargs):
        self.equipment = kwargs.pop("equipment", None)
        super().__init__(*args, **kwargs)

        if self.equipment:
            self.fields["new_status"].initial = self.equipment.status
            self.fields["to_employee"].initial = self.equipment.assigned_to_id

        for _, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"

    def clean_to_employee(self):
        emp = self.cleaned_data.get("to_employee")

        if emp and emp.organization_id != self.equipment.organization_id:
            raise forms.ValidationError("Сотрудник не принадлежит организации оборудования.")
        return emp
