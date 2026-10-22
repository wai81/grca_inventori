from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, UpdateView, DetailView
from django_filters.views import FilterView

from config.pdf import render_pdf_response
from apps.directory.filters import EmployeeFilter, OrganizationFilter, DepartmentFilter
from apps.directory.forms import OrganizationForm, DepartmentForm, EmployeeForm, EmployeeUnassignAllForm
from apps.directory.models import Employee, Organization, Department
from apps.inventory.models import Equipment, EquipmentStatus
from apps.inventory.services import change_equipment
from apps.inventory.views import _append_query
from apps.directory.access import filter_queryset_by_user_orgs, user_has_org_access, safe_next_url

class SetAuthorMixin:
    """Отмечает текущего пользователя автором создания/изменения записи."""

    def form_valid(self, form):
        form.instance.set_author(self.request.user)
        return super().form_valid(form)


class EmployeeListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    permission_required = "directory.view_employee"
    template_name = "directory/employee_list.html"
    model = Employee
    filterset_class = EmployeeFilter
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Employee.objects
            .select_related("organization", "department")
            .order_by("-active", "full_name")
        )

        return filter_queryset_by_user_orgs(qs, self.request.user, "organization")

class EmployeeDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "directory.view_employee"
    model = Employee
    template_name = "directory/employee_detail.html"

    def get_queryset(self):
        qs = Employee.objects.select_related("organization", "department")
        return filter_queryset_by_user_orgs(qs, self.request.user, "organization")

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
        employee = get_object_or_404(
            filter_queryset_by_user_orgs(Employee.objects.all(), request.user, "organization"), pk=pk)

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
            for eq in items:
                change_equipment(
                    eq, request.user,
                    to_employee=None,
                    new_status=reserve_value,
                    document_number=doc_no,
                    comment=comment,
                )

        if items:
            messages.success(request, f"Снято в резерв: {len(items)}")
        else:
            messages.info(request, "У сотрудника нет закреплённого оборудования.")

        return redirect("directory:employee_detail", pk=employee.pk)

class EmployeeCreateView(LoginRequiredMixin, PermissionRequiredMixin, SetAuthorMixin, CreateView):
    permission_required = "directory.add_employee"
    model = Employee
    form_class = EmployeeForm
    template_name = "directory/employee_form.html"
    success_url = reverse_lazy("directory:employee_list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def get_initial(self):
        initial = super().get_initial()
        org_id = self.request.GET.get("org_id") or self.request.POST.get("org_id")
        department_id = self.request.GET.get("department") or self.request.POST.get("department")

        if org_id:
            initial["organization"] = org_id
        if department_id:
            initial["department"] = department_id

        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next"] = self.request.GET.get("next") or self.request.POST.get("next") or ""
        ctx["org_id"] = self.request.GET.get("org_id") or self.request.POST.get("org_id") or ""
        return ctx

    def get_success_url(self):
        nxt = safe_next_url(self.request, self.request.POST.get("next") or self.request.GET.get("next"))
        org_id = self.request.POST.get("org_id") or self.request.GET.get("org_id") or ""
        if nxt:
            url = _append_query(nxt, assigned_to=self.object.pk)
            if org_id:
                url = _append_query(url, organization=org_id)
            return url
        return super().get_success_url()




class EmployeeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SetAuthorMixin, UpdateView):
    permission_required = "directory.change_employee"
    model = Employee
    form_class = EmployeeForm
    template_name = "directory/employee_form.html"
    success_url = reverse_lazy("directory:employee_list")

    def get_queryset(self):
        qs = Employee.objects.select_related("organization", "department")
        return filter_queryset_by_user_orgs(qs, self.request.user, "organization")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw


class EmployeeToggleActiveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "directory.change_employee"

    # Используем как “Удалить” (active=False) и “Восстановить” (active=True)
    def post(self, request, pk):
        qs = Employee.objects.select_related("organization")
        qs = filter_queryset_by_user_orgs(qs, request.user, "organization")
        obj = get_object_or_404(qs, pk=pk)
        obj.active = not obj.active
        obj.set_author(request.user)
        obj.save(update_fields=["active", "updated_by"])
        return redirect(safe_next_url(request, request.POST.get("next") or request.META.get("HTTP_REFERER"),
                                      reverse("directory:employee_list")))

class EmployeeListPdfView(EmployeeListView):
    permission_required = "directory.view_employee"

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        filt = self.get_filterset(self.filterset_class)
        context = {"filter": filt, "request": request}
        return render_pdf_response(request, "directory/pdf/employee_list_pdf.html", context, "employees.pdf")


class OrganizationListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    permission_required = "directory.view_organization"
    template_name = "directory/organization_list.html"
    filterset_class = OrganizationFilter
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Organization.objects
            .annotate(
                departments_count=Count("departments", distinct=True),
                employees_count=Count("employees", distinct=True),
            )
            .order_by("-active", "code", "name")
        )

        return filter_queryset_by_user_orgs(qs, self.request.user, "id")


class OrganizationToggleActiveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "directory.change_organization"

    def post(self, request, pk):
        qs = filter_queryset_by_user_orgs(Organization.objects.all(), request.user, "id")
        obj = get_object_or_404(qs, pk=pk)
        obj.active = not obj.active
        obj.save(update_fields=["active"])

        return redirect(safe_next_url(request, request.POST.get("next") or request.META.get("HTTP_REFERER"),
                                      reverse("directory:organization_list")))


class OrganizationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "directory.add_organization"
    model = Organization
    form_class = OrganizationForm
    template_name = "directory/organization_form.html"
    success_url = reverse_lazy("directory:organization_list")


class OrganizationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "directory.change_organization"
    model = Organization
    form_class = OrganizationForm
    template_name = "directory/organization_form.html"
    success_url = reverse_lazy("directory:organization_list")

    def get_queryset(self):
        return filter_queryset_by_user_orgs(Organization.objects.all(), self.request.user, "id")


class DepartmentListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    permission_required = "directory.view_department"
    template_name = "directory/department_list.html"
    filterset_class = DepartmentFilter
    # подразделения выводятся группами по организациям, поэтому страница большая
    paginate_by = 300

    def get_queryset(self):
        qs = (
            Department.objects
            .select_related("organization")
            .annotate(
                employees_count=Count("employees", filter=Q(employees__active=True), distinct=True),
                equipment_count=Count("employees__assigned_equipment", distinct=True),
            )
            .order_by("organization__code", "-active", "name")
        )
        return filter_queryset_by_user_orgs(qs, self.request.user, "organization")

class DepartmentsByOrganizationView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "directory.view_department"

    def get(self, request):
        org_id = request.GET.get("organization_id")
        if not org_id:
            return JsonResponse({"results": []})

        if not user_has_org_access(request.user, org_id):
            return JsonResponse({"results": []})

        q = (request.GET.get("q") or "").strip()

        qs = Department.objects.filter(organization_id=org_id, active=True)

        if q:
            qs = qs.filter(name__icontains=q)

        qs = qs.order_by("name")[:50]

        data = [{"id": d.id, "name": d.name} for d in qs]  # <-- без повторного order_by
        return JsonResponse({"results": data})

class DepartmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, SetAuthorMixin, CreateView):
    permission_required = "directory.add_department"
    model = Department
    form_class = DepartmentForm
    template_name = "directory/department_form.html"
    success_url = reverse_lazy("directory:department_list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def get_initial(self):
        initial = super().get_initial()
        org_id = self.request.GET.get("org_id") or self.request.POST.get("org_id")
        if org_id:
            initial["organization"] = org_id
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next"] = self.request.GET.get("next") or self.request.POST.get("next") or ""
        ctx["org_id"] = self.request.GET.get("org_id") or self.request.POST.get("org_id") or ""
        return ctx

    def get_success_url(self):
        nxt = safe_next_url(self.request, self.request.POST.get("next") or self.request.GET.get("next"))
        if nxt:
            return _append_query(
                nxt,
                org_id=self.object.organization_id,
                department=self.object.pk,
            )
        return super().get_success_url()


class DepartmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SetAuthorMixin, UpdateView):
    permission_required = "directory.change_department"
    model = Department
    form_class = DepartmentForm
    template_name = "directory/department_form.html"
    success_url = reverse_lazy("directory:department_list")

    def get_queryset(self):
        qs = Department.objects.select_related("organization")
        return filter_queryset_by_user_orgs(qs, self.request.user, "organization")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw


class DepartmentToggleActiveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "directory.change_department"

    def post(self, request, pk):
        qs = Department.objects.select_related("organization")
        qs = filter_queryset_by_user_orgs(qs, request.user, "organization")
        obj = get_object_or_404(qs, pk=pk)
        obj.active = not obj.active
        obj.set_author(request.user)
        obj.save(update_fields=["active", "updated_by"])
        return redirect(safe_next_url(request, request.POST.get("next") or request.META.get("HTTP_REFERER"),
                                      reverse("directory:department_list")))