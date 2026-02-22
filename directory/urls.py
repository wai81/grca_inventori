from django.urls import path
from . import views

app_name = "directory"

urlpatterns = [
    path("employees/", views.EmployeeListView.as_view(), name="employee_list"),

    path("employees/pdf/", views.EmployeeListPdfView.as_view(), name="employee_list_pdf"),

    path("organizations/", views.OrganizationListView.as_view(), name="organization_list"),
    path("organizations/create/", views.OrganizationCreateView.as_view(), name="organization_create"),
    path("organizations/<int:pk>/edit/", views.OrganizationUpdateView.as_view(), name="organization_edit"),
    path("organizations/<int:pk>/toggle-active/", views.OrganizationToggleActiveView.as_view(), name="organization_toggle_active"),

    path("departments/", views.DepartmentListView.as_view(), name="department_list"),
]