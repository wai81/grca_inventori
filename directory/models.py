from django.db import models

class Organization(models.Model):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=200, unique=True)
    active = models.BooleanField(default=False, verbose_name="Активна")

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"

    def __str__(self):
        return f"{self.code} {self.name}"


class Department(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=200)

    class Meta:
        verbose_name = "Подразделение"
        verbose_name_plural = "Подразделения"
        unique_together = [("organization", "name")]

    def __str__(self):
        return f"{self.organization} / {self.name}"


class Employee(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="employees")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        indexes = [
            models.Index(fields=["full_name"]),
            models.Index(fields=["organization", "department"]),
        ]

    def __str__(self):
        return self.full_name