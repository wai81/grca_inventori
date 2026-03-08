from django.forms import (
    Select, SelectMultiple, CheckboxInput, CheckboxSelectMultiple, RadioSelect,
    Textarea, DateInput
)

class BootstrapFilterFormMixin:
    """
    Автоматически добавляет Bootstrap 5 классы виджетам в django-filter form.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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