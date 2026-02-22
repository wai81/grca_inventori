from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django_filters.views import FilterView

from directory.filters import EmployeeFilter
from directory.models import Employee


# Create your views here.
class EmployeeListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    permission_required = "inventory.view_employee"
    template_name = "inventory/employee_list.html"
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
        return render_pdf_response(request, "inventory/pdf/employee_list_pdf.html", context, "employees.pdf")

