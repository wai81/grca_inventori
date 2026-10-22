from django.contrib import admin

from apps.directory.models import Organization, Department, Employee, UserOrganizationAccess


@admin.register(UserOrganizationAccess)
class UserOrganizationAccessAdmin(admin.ModelAdmin):
    list_display = ("user",)
    search_fields = ("user__username", "user__full_name", "user__email")
    filter_horizontal = ("organizations",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id","code", "name","active")
    search_fields = ("code", "name",)
    list_filter =("active",)


class AuthorAdminMixin:
    """Заполняет created_by/updated_by при сохранении из админки."""
    readonly_fields = ("created_by", "created_at", "updated_by", "updated_at")

    def save_model(self, request, obj, form, change):
        obj.set_author(request.user)
        super().save_model(request, obj, form, change)


@admin.register(Department)
class DepartmentAdmin(AuthorAdminMixin, admin.ModelAdmin):
    list_display = ("id","organization", "name","active")
    search_fields = ("name",)
    list_filter =("organization","active")

@admin.register(Employee)
class EmployeeAdmin(AuthorAdminMixin, admin.ModelAdmin):
    list_display = ("id","full_name", "organization","department","active")
    search_fields = ("full_name","organization__name")
    list_filter = ("organization","department","active")