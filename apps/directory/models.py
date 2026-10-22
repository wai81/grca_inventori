from django.db import models
from django.utils import timezone

from config import settings


class AuthorFieldsMixin(models.Model):
    """Кто и когда создал / последним изменил запись."""
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="%(class)s_created", verbose_name="Создал",
    )
    # null — для записей, созданных до появления поля (дата неизвестна)
    created_at = models.DateTimeField("Создан", null=True, blank=True, editable=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="%(class)s_updated", verbose_name="Изменил",
    )
    updated_at = models.DateTimeField("Изменён", auto_now=True, null=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self._state.adding and self.created_at is None:
            self.created_at = timezone.now()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "updated_at" not in update_fields:
            # auto_now срабатывает только для полей из update_fields
            kwargs["update_fields"] = list(update_fields) + ["updated_at"]
        super().save(*args, **kwargs)

    def set_author(self, user):
        """Отметить автора изменения (и создания — для новой записи)."""
        if user is not None and not getattr(user, "is_authenticated", True):
            user = None
        if self._state.adding and self.created_by_id is None:
            self.created_by = user
        self.updated_by = user


class Organization(models.Model):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=200, unique=True)
    active = models.BooleanField(default=True, verbose_name="Активна")

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"


class UserOrganizationAccess(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_access",
        verbose_name="Пользователь",
    )
    organizations = models.ManyToManyField(
        "Organization",
        blank=True,
        related_name="user_accesses",
        verbose_name="Доступные организации",
    )

    class Meta:
        verbose_name = "Доступ пользователя к организациям"
        verbose_name_plural = "Доступы пользователей к организациям"

    def __str__(self):
        return self.user.get_username()


class Department(AuthorFieldsMixin):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="departments", verbose_name="Организация")
    name = models.CharField(max_length=200,verbose_name="Наименование")
    active = models.BooleanField(default=True, verbose_name="Активно")

    class Meta:
        verbose_name = "Подразделение"
        verbose_name_plural = "Подразделения"
        unique_together = [("organization", "name")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.organization} / {self.name}"


class Employee(AuthorFieldsMixin):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="employees", verbose_name="Организация")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees", verbose_name="Подразделение")
    full_name = models.CharField(max_length=200, verbose_name="Ф.И.О.")
    email = models.EmailField(blank=True, verbose_name="e-mail")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Телефон")
    active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        indexes = [
            models.Index(fields=["full_name"]),
            models.Index(fields=["organization", "department"]),
        ]
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name