from django.forms import (
    Select, SelectMultiple, CheckboxInput, CheckboxSelectMultiple, RadioSelect,
    Textarea, DateInput, ModelChoiceField
)

from apps.directory.access import get_allowed_organizations


class BootstrapFilterFormMixin:
    """
    Автоматически добавляет Bootstrap 5 классы виджетам в django-filter form
    и ограничивает выпадающие списки организациями текущего пользователя.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        user = getattr(self.request, "user", None)
        allowed_orgs = None
        if user is not None and not user.is_superuser:
            allowed_orgs = get_allowed_organizations(user)

        for _, field in self.form.fields.items():
            w = field.widget

            if isinstance(w, (CheckboxInput, CheckboxSelectMultiple, RadioSelect)):
                css = "form-check-input"
            elif isinstance(w, (Select, SelectMultiple)):
                css = "form-select"
            else:
                css = "form-control"

            w.attrs["class"] = (w.attrs.get("class", "") + " " + css).strip()

            # Дата-поля красиво (календарь браузера)
            if isinstance(w, DateInput):
                w.attrs.setdefault("type", "date")

            if allowed_orgs is not None and isinstance(field, ModelChoiceField):
                model_name = field.queryset.model._meta.label
                if model_name == "directory.Organization":
                    field.queryset = field.queryset.filter(pk__in=allowed_orgs)
                elif model_name in ("directory.Department", "directory.Employee"):
                    field.queryset = field.queryset.filter(organization__in=allowed_orgs)
