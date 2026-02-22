from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count
from django.shortcuts import render
from django_filters.views import FilterView

from config.pdf import render_pdf_response
from directory.filters import EmployeeFilter, OrganizationFilter
from directory.models import Employee, Organization


# Create your views here.
class EmployeeListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    permission_required = "directory.view_employee"
    template_name = "directory/employee_list.html"
    model = Employee
    filterset_class = EmployeeFilter
    paginate_by = 25

    def get_queryset(self):
        return Employee.objects.select_related("organization", "department")


class EmployeeListPdfView(EmployeeListView):
    permission_required = "inventory.view_employee"

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        filt = self.get_filterset(self.filterset_class)
        context = {"filter": filt, "request": request}
        return render_pdf_response(request, "directory/pdf/employee_list_pdf.html", context, "employees.pdf")


class OrganizationListView(FilterView):
    template_name = "directory/organization_list.html"
    filterset_class = OrganizationFilter
    paginate_by = 20
    def get_queryset(self):
        return (
            Organization.objects
            .annotate(
                departments_count=Count("departments", distinct=True),
                employees_count=Count("employees", distinct=True),
            )
            .order_by("code", "name")
        )