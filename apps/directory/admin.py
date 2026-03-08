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