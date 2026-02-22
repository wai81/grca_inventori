from django import forms
from .models import Organization, Department, Employee


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ["code", "name", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", "") == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["organization", "name", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            if getattr(field.widget, "input_type", "") == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["organization", "department", "full_name", "email", "phone", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # чтобы не выбирать “чужой” отдел
        org_id = None
        if self.is_bound:
            org_id = self.data.get("organization") or None
        elif self.instance and getattr(self.instance, "organization_id", None):
            org_id = self.instance.organization_id

        if org_id:
            self.fields["department"].queryset = Department.objects.filter(
                organization_id=org_id,
                active=True,
            ).order_by("name")
        else:
            self.fields["department"].queryset = Department.objects.none()

        self.fields["department"].empty_label = "— сначала выберите организацию —"


        for _, field in self.fields.items():
            if getattr(field.widget, "input_type", "") == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = ""  # или свой класс, без рамки
            else:
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned = super().clean()
        org = cleaned.get("organization")
        dept = cleaned.get("department")
        if org and dept and dept.organization_id != org.id:
            self.add_error("department", "Подразделение не принадлежит выбранной организации")
        return cleaned