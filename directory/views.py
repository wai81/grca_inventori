from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, UpdateView, DetailView
from django_filters.views import FilterView

from config.pdf import render_pdf_response
from directory.filters import EmployeeFilter, OrganizationFilter, DepartmentFilter
from directory.forms import OrganizationForm, DepartmentForm, EmployeeForm, EmployeeUnassignAllForm
from directory.models import Employee, Organization, Department
from inventory.models import Equipment, EquipmentEvent, EquipmentEventType, EquipmentStatus
from inventory.views import _append_query


# Create your views here.
class EmployeeListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    permission_required = "directory.view_employee"
    template_name = "directory/employee_list.html"
    model = Employee
    filterset_class = EmployeeFilter
    paginate_by = 25

    def get_queryset(self):
        return (
            Employee.objects
            .select_related("organization", "department")
            .order_by("-active", "full_name")
        )

class EmployeeDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "directory.view_employee"
    model = Employee
    template_name = "directory/employee_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        if self.request.user.has_perm("inventory.view_equipment"):
            qs = (
                Equipment.objects
                .filter(assigned_to=self.object)
                .select_related("organization", "equipment_type", "assigned_to", "assigned_to__department")
                .order_by("equipment_type__name", "name")
            )
        else:
            qs = Equipment.objects.none()

        ctx["assigned_equipment"] = qs
        ctx["assigned_equipment_count"] = qs.count()

        ctx["unassign_form"] = ctx.get("unassign_form") or EmployeeUnassignAllForm()
        ctx["show_unassign_modal"] = ctx.get("show_unassign_modal", False)
        return ctx

class EmployeeUnassignAllView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = ("directory.view_employee", "inventory.change_equipment")

    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)

        form = EmployeeUnassignAllForm(request.POST)
        if not form.is_valid():
            # вернемся на карточку с ошибками и открытой модалкой
            dv = EmployeeDetailView()
            dv.request = request
            dv.object = employee
            ctx = dv.get_context_data(unassign_form=form, show_unassign_modal=True)
            return dv.render_to_response(ctx)

        # Найдём значение статуса "резерв" из choices (чтобы не зависеть от ключа)
        reserve_value = None
        for k, v in EquipmentStatus.choices:
            if str(v).strip().lower().startswith("резерв"):
                reserve_value = k
                break
        if reserve_value is None:
            messages.error(request, "Статус “резерв” не найден в EquipmentStatus.")
            return redirect("directory:employee_detail", pk=employee.pk)

        doc_no = form.cleaned_data["document_number"].strip()
        comment = form.cleaned_data["comment"].strip()

        qs = Equipment.objects.filter(assigned_to=employee).select_for_update()

        with transaction.atomic():
            items = list(qs)

            events = []
            for eq in items:
                old_status = eq.status
                eq.assigned_to = None
                eq.status = reserve_value
                eq.save(update_fields=["assigned_to", "status"])

                events.append(EquipmentEvent(
                    equipment=eq,
                    event_type=EquipmentEventType.MOVE,
                    from_employee=employee,
                    to_employee=None,
                    old_status=old_status if old_status != reserve_value else "",
                    new_status=reserve_value if old_status != reserve_value else "",
                    document_number=doc_no,
                    comment=comment,
                ))

            if events:
                EquipmentEvent.objects.bulk_create(events)

        if items:
            messages.success(request, f"Снято в резерв: {len(items)}")
        else:
            messages.info(request, "У сотрудника нет закреплённого оборудования.")

        return redirect("directory:employee_detail", pk=employee.pk)

class EmployeeCreateView(LoginRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next"] = self.request.GET.get("next") or self.request.POST.get("next") or ""
        ctx["org_id"] = self.request.GET.get("org_id") or self.request.POST.get("org_id") or ""
        return ctx

    def get_success_url(self):
        nxt = self.request.POST.get("next") or self.request.GET.get("next") or ""
        org_id = self.request.POST.get("org_id") or self.request.GET.get("org_id") or ""
        if nxt:
            url = _append_query(nxt, assigned_to=self.object.pk)
            if org_id:
                url = _append_query(url, organization=org_id)
            return url
        return super().get_success_url()

    template_name = "directory/employee_form.html"
    success_url = reverse_lazy("directory:employee_list")


class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "directory/employee_form.html"
    success_url = reverse_lazy("directory:employee_list")


class EmployeeToggleActiveView(LoginRequiredMixin, View):
    # Используем как “Удалить” (active=False) и “Восстановить” (active=True)
    def post(self, request, pk):
        obj = get_object_or_404(Employee, pk=pk)
        obj.active = not obj.active
        obj.save(update_fields=["active"])
        return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "/employees/")

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

class DepartmentsByOrganizationView(LoginRequiredMixin, View):
    permission_required = "directory.view_department"

    def get(self, request):
        org_id = request.GET.get("organization_id")
        if not org_id:
            return JsonResponse({"results": []})

        q = (request.GET.get("q") or "").strip()

        qs = Department.objects.filter(organization_id=org_id, active=True)

        if q:
            qs = qs.filter(name__icontains=q)

        qs = qs.order_by("name")[:50]

        data = [{"id": d.id, "name": d.name} for d in qs]  # <-- без повторного order_by
        return JsonResponse({"results": data})

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