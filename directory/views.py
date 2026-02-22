from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, UpdateView
from django_filters.views import FilterView

from config.pdf import render_pdf_response
from directory.filters import EmployeeFilter, OrganizationFilter, DepartmentFilter
from directory.forms import OrganizationForm, DepartmentForm
from directory.models import Employee, Organization, Department


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
    permission_required = "directory.view_employee"

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
            .order_by("-active", "code", "name")
        )


class OrganizationToggleActiveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(Organization, pk=pk)
        obj.active = not obj.active
        obj.save(update_fields=["active"])

        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/organizations/"
        return redirect(next_url)


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "directory/organization_form.html"
    success_url = reverse_lazy("directory:organization_list")


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "directory/organization_form.html"
    success_url = reverse_lazy("directory:organization_list")


class DepartmentListView(LoginRequiredMixin, FilterView):
    template_name = "directory/department_list.html"
    filterset_class = DepartmentFilter
    paginate_by = 20

    def get_queryset(self):
        return (
            Department.objects
            .select_related("organization")
            .annotate(employees_count=Count("employees", distinct=True))
            .order_by("-active","organization__code", "name")
        )


class DepartmentCreateView(LoginRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "directory/department_form.html"
    success_url = reverse_lazy("directory:department_list")


class DepartmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "directory/department_form.html"
    success_url = reverse_lazy("directory:department_list")


class DepartmentToggleActiveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(Department, pk=pk)
        obj.active = not obj.active
        obj.save(update_fields=["active"])
        return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "/departments/")