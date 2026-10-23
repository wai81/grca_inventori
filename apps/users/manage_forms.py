from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Group

from apps.directory.models import Organization, UserOrganizationAccess
from apps.inventory.roles import ROLE_VIEWER, bootstrap_roles

from .models import User
from .profile import PERMISSION_ACTIONS, PERMISSION_AREAS
from .role_utils import SYSTEM_ROLES, is_system, ordered_roles, role_label, set_role_permissions


def role_choices():
    return [("", "Без роли")] + [(g.name, role_label(g.name)) for g in ordered_roles()]


def user_role(user):
    """Имя роли пользователя (его группа) или пустая строка."""
    names = [g.name for g in user.groups.all()]
    for name in reversed(SYSTEM_ROLES):  # при нескольких ролях берём старшую системную
        if name in names:
            return name
    return sorted(names)[0] if names else ""


def _bootstrap(form):
    for name, field in form.fields.items():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "form-check-input")
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", "form-select")
        else:
            widget.attrs.setdefault("class", "form-control")


class UserManageForm(forms.ModelForm):
    role = forms.ChoiceField(label="Роль", choices=(), required=False)
    organizations = forms.ModelMultipleChoiceField(
        label="Доступные организации",
        queryset=Organization.objects.order_by("code"),
        required=False,
        help_text="Пользователь видит оборудование, сотрудников и подразделения только этих организаций.",
    )

    class Meta:
        model = User
        fields = ("username", "last_name", "first_name", "email", "telegram_id", "is_active", "is_superuser")
        labels = {
            "username": "Логин",
            "last_name": "Фамилия",
            "first_name": "Имя",
            "email": "E-mail",
            "telegram_id": "Telegram ID",
            "is_active": "Активен (может входить)",
            "is_superuser": "Суперпользователь (все права и все организации)",
        }
        help_texts = {
            "username": "Буквы, цифры и символы @/./+/-/_",
            "telegram_id": "Числовой ID из Telegram — нужен для работы через бота.",
            "is_active": "Снимите, чтобы запретить вход, не удаляя пользователя.",
            "is_superuser": "Может управлять пользователями; роль и организации не учитываются.",
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user
        self.fields["role"].choices = role_choices()
        if self.instance.pk:
            self.fields["role"].initial = user_role(self.instance)
            access = getattr(self.instance, "organization_access", None)
            if access:
                self.fields["organizations"].initial = list(access.organizations.values_list("pk", flat=True))
        # себе нельзя снять суперпользователя или заблокировать вход
        if self.is_self:
            for name in ("is_active", "is_superuser"):
                self.fields[name].disabled = True
                self.fields[name].help_text = "Нельзя изменить для своей учётной записи."
        _bootstrap(self)
        self.fields["organizations"].widget.attrs["placeholder"] = "Выберите организации"

    @property
    def is_self(self):
        return bool(self.instance.pk and self.current_user and self.instance.pk == self.current_user.pk)

    def clean_telegram_id(self):
        value = self.cleaned_data.get("telegram_id")
        if value and User.objects.filter(telegram_id=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Этот Telegram ID уже привязан к другому пользователю.")
        return value

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self.save_access(user)
        return user

    def save_access(self, user):
        """Роль (группа inventory_*) и доступ к организациям."""
        role = self.cleaned_data.get("role") or ""
        group = None
        if role:
            group = Group.objects.filter(name=role).first()
            if group is None and is_system(role):
                group = bootstrap_roles()[role]
        # у пользователя одна роль
        user.groups.set([group] if group else [])

        access, _ = UserOrganizationAccess.objects.get_or_create(user=user)
        access.organizations.set(self.cleaned_data.get("organizations") or [])


class UserCreateForm(UserManageForm):
    password1 = forms.CharField(label="Пароль", strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Повторите пароль", strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_active"].initial = True
        if any(v == ROLE_VIEWER for v, _ in self.fields["role"].choices):
            self.fields["role"].initial = ROLE_VIEWER

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Пароли не совпадают.")
        elif p1:
            try:
                password_validation.validate_password(p1, self.instance)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_access(user)
        return user


class UserSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Новый пароль"
        self.fields["new_password2"].label = "Повторите пароль"
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control", "autocomplete": "new-password"})


class RoleForm(forms.Form):
    """Название роли и матрица прав: поля perm__<app>__<model>__<action>."""
    name = forms.CharField(label="Название роли", max_length=150)

    def __init__(self, *args, group=None, initial_rows=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        self.fields["name"].widget.attrs.update({"class": "form-control", "placeholder": "Например: Бухгалтерия"})
        if group is not None:
            self.fields["name"].initial = role_label(group.name)
            if is_system(group):
                self.fields["name"].disabled = True
                self.fields["name"].help_text = "Системную роль переименовать нельзя."
        for row in initial_rows or []:
            for cell in row["cells"]:
                self.fields[cell["name"]] = forms.BooleanField(required=False, initial=cell["allowed"])

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if self.group is not None and is_system(self.group):
            return self.group.name
        taken = {role_label(g.name).lower() for g in Group.objects.exclude(pk=getattr(self.group, "pk", None))}
        taken |= {g.lower() for g in Group.objects.exclude(pk=getattr(self.group, "pk", None))
                  .values_list("name", flat=True)}
        if name.lower() in taken:
            raise forms.ValidationError("Роль с таким названием уже есть.")
        return name

    def selected(self):
        """{(app, model, action)}; изменение/создание/удаление без просмотра невозможно — просмотр добавляется."""
        result = set()
        for _, app, model in PERMISSION_AREAS:
            actions = {a for a, _ in PERMISSION_ACTIONS if self.cleaned_data.get(f"perm__{app}__{model}__{a}")}
            if actions:
                actions.add("view")
            result |= {(app, model, a) for a in actions}
        return result

    def save(self):
        group = self.group or Group()
        group.name = self.cleaned_data["name"]
        group.save()
        set_role_permissions(group, self.selected())
        return group
