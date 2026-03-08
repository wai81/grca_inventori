from django import forms
from .models import Organization, Department, Employee
from .access import get_allowed_organizations


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
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user and not user.is_superuser:
            self.fields["organization"].queryset = get_allowed_organizations(user).order_by("code", "name")

        for _, field in self.fields.items():
            if getattr(field.widget, "input_type", "") == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

    class Meta:
        model = Department
        fields = ["organization", "name", "active"]



class EmployeeForm(forms.ModelForm):

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        allowed_orgs = Organization.objects.none()
        if user:
            allowed_orgs = get_allowed_organizations(user)

        if not user or not user.is_superuser:
            self.fields["organization"].queryset = allowed_orgs.order_by("code", "name")

        # чтобы не выбирать “чужой” отдел
        org_id = None
        if self.data.get("organization"):
            org_id = self.data.get("organization")
        elif self.instance.pk and self.instance.organization_id:
            org_id = self.instance.organization_id
        elif self.initial.get("organization"):
            org_id = self.initial.get("organization")

        dept_qs = Department.objects.none()
        if org_id:
            dept_qs = Department.objects.filter(organization_id=org_id)
            if user and not user.is_superuser:
                dept_qs = dept_qs.filter(organization__in=allowed_orgs)

        self.fields["department"].queryset = dept_qs.order_by("name")

        # if self.is_bound:
        #     org_id = self.data.get("organization") or None
        # elif self.instance and getattr(self.instance, "organization_id", None):
        #     org_id = self.instance.organization_id
        #
        # if org_id:
        #     self.fields["department"].queryset = Department.objects.filter(
        #         organization_id=org_id,
        #         active=True,
        #     ).order_by("name")
        # else:
        #     self.fields["department"].queryset = Department.objects.none()
        #
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

    class Meta:
        model = Employee
        fields = ["organization", "department", "full_name", "email", "phone", "active"]


class EmployeeUnassignAllForm(forms.Form):
    document_number = forms.CharField(
        label="Номер документа",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )
    confirm = forms.BooleanField(
        label="Понимаю последствия (снять всё в резерв)",
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )