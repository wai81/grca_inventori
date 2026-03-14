from django.db import models

from config import settings


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


class Department(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True, verbose_name="Активно")

    class Meta:
        verbose_name = "Подразделение"
        verbose_name_plural = "Подразделения"
        unique_together = [("organization", "name")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.organization} / {self.name}"


class Employee(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="employees")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
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