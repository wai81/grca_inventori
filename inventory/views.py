from io import BytesIO
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import ProtectedError, Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView, UpdateView, FormView, CreateView, DeleteView, ListView
from django_filters.views import FilterView

from directory.models import Employee
from inventory.filters import EquipmentFilter
from inventory.form import EquipmentForm, EquipmentMoveForm, EquipmentTypeForm
from inventory.models import InventoryDocument, Equipment, EquipmentEventType, EquipmentEvent, EquipmentType
from config.pdf import render_pdf_response
from inventory.services import apply_document


class EquipmentListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    permission_required = "inventory.view_equipment"
    template_name = "inventory/equipment_list.html"
    model = Equipment

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["equipmenttype_meta"] = list(EquipmentType.objects.values("id", "category"))
        return ctx

    filterset_class = EquipmentFilter
    paginate_by = 25

    def get_queryset(self):
        return Equipment.objects.select_related("organization", "equipment_type", "assigned_to", "assigned_to__department")


class EquipmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "inventory.change_equipment"
    model = Equipment
    form_class = EquipmentForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["equipmenttype_meta"] = list(EquipmentType.objects.values("id", "category"))
        return ctx

    template_name = "inventory/equipment_form.html"
    success_url = reverse_lazy("inventory:equipment_list")

class EquipmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "inventory.add_equipment"
    model = Equipment
    form_class = EquipmentForm

    def get_initial(self):
        ini = super().get_initial()

        et = self.request.GET.get("equipment_type")
        if et:
            ini["equipment_type"] = et

        emp = self.request.GET.get("assigned_to")
        if emp:
            ini["assigned_to"] = emp

        org = self.request.GET.get("organization")
        if org:
            ini["organization"] = org

        return ini

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["equipmenttype_meta"] = list(EquipmentType.objects.values("id", "category"))
        return ctx

    template_name = "inventory/equipment_form.html"
    success_url = reverse_lazy("inventory:equipment_list")

class EquipmentMoveView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "inventory.change_equipment"
    template_name = "inventory/equipment_move_form.html"
    form_class = EquipmentMoveForm

    def dispatch(self, request, *args, **kwargs):
        self.equipment = get_object_or_404(Equipment, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["equipment"] = self.equipment
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.equipment
        return ctx

    def form_valid(self, form):
        eq = self.equipment
        from_emp = eq.assigned_to
        to_emp = form.cleaned_data["to_employee"]
        new_status = form.cleaned_data["new_status"]
        doc_no = (form.cleaned_data.get("document_number") or "").strip()
        comment = (form.cleaned_data.get("comment") or "").strip()

        old_status = eq.status

        with transaction.atomic():
            eq.assigned_to = to_emp
            eq.status = new_status
            eq.save()

        EquipmentEvent.objects.create(
            equipment=eq,
            event_type=EquipmentEventType.MOVE,
            from_employee=from_emp,
            to_employee=to_emp,
            old_status=old_status if old_status != new_status else "",
            new_status=new_status if old_status != new_status else "",
            document_number=doc_no,
            comment=comment,
        )

        messages.success(self.request, "Перемещение сохранено.")
        return redirect("inventory:equipment_detail", pk=eq.pk)

class EquipmentListPdfView(EquipmentListView):
    permission_required = "inventory.view_equipment"

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        filt = self.get_filterset(self.filterset_class)
        context = {"filter": filt, "request": request}
        return render_pdf_response(request, "inventory/pdf/equipment_list_pdf.html", context, "equipment.pdf")


class EquipmentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "inventory.view_equipment"
    template_name = "inventory/equipment_detail.html"
    model = Equipment

    def get_queryset(self):
        return Equipment.objects.select_related("organization", "equipment_type", "assigned_to", "assigned_to__department").prefetch_related("events")


class DocumentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "inventory.view_inventorydocument"
    template_name = "inventory/document_detail.html"
    model = InventoryDocument

    def get_queryset(self):
        return InventoryDocument.objects.select_related("organization", "from_employee", "to_employee").prefetch_related("lines", "lines__equipment")


class DocumentPdfView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "inventory.view_inventorydocument"
    model = InventoryDocument

    def get_queryset(self):
        return InventoryDocument.objects.select_related("organization", "from_employee", "to_employee").prefetch_related("lines")

    def get(self, request, *args, **kwargs):
        doc = self.get_object()
        if doc.doc_type == "transfer":
            tpl = "inventory/pdf/act_transfer.html"
            fname = f"act-transfer-{doc.number}.pdf"
        else:
            tpl = "inventory/pdf/act_writeoff.html"
            fname = f"act-writeoff-{doc.number}.pdf"
        return render_pdf_response(request, tpl, {"doc": doc}, fname)


class EmployeesByOrganizationView(LoginRequiredMixin, View):
    permission_required = "directory.view_department"

    def get(self, request):
        org_id = request.GET.get("organization_id")
        if not org_id:
            return JsonResponse({"results": []})

        q = (request.GET.get("q") or "").strip()

        qs = (Employee.objects.filter(
            organization_id=org_id,
            active=True
        ).select_related("department").order_by("full_name"))


        if q:
            qs = qs.filter(full_name__icontains=q)

        data = [
            {"id": e.id, "name": e.full_name,  "department": (e.department.name if e.department else "")}
            for e in qs[:200]
        ]
        return JsonResponse({"results": data})


def equipment_qr_png(request, pk: int):
    """
    PNG QR-код, который ведет на карточку оборудования.
    """
    equipment = get_object_or_404(Equipment, pk=pk)
    url = request.build_absolute_uri(reverse("inventory:equipment_detail", args=[equipment.pk]))

    import qrcode
    img = qrcode.make(url)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")


def equipment_qr_label(request, pk: int):
    """
    Страница-этикетка (шаблон) для печати: QR + ключевые поля.
    """
    equipment = get_object_or_404(Equipment, pk=pk)
    # return render(request, "inventory/equipment_qr_label.html", {"object": equipment})
    return render(request, "inventory/equipment_qr_label_58x40.html", {"object": equipment})


def apply_document_view(request, pk: int):
    """
    Применение акта (обновляет закрепления/статусы по строкам).
    Ограничиваем правом change_inventorydocument.
    """
    if not request.user.is_authenticated:
        return redirect("login")

    if not request.user.has_perm("inventory.change_inventorydocument"):
        return redirect("inventory:document_detail", pk=pk)

    doc = get_object_or_404(InventoryDocument, pk=pk)
    apply_document(doc)
    return redirect("inventory:document_detail", pk=pk)

def _append_query(url: str, **params) -> str:
    parts = urlsplit(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    for k, v in params.items():
        q[k] = str(v)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


class EquipmentTypeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "inventory.view_equipmenttype"
    template_name = "inventory/equipmenttype_list.html"
    model = EquipmentType
    def get_queryset(self):
        return (
            EquipmentType.objects
            .annotate(
                equipment_count=Count("equipment", distinct=True),
            )
        )

    paginate_by = 25
    ordering = ["name"]


class EquipmentTypeDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "inventory.view_equipmenttype"
    template_name = "inventory/equipmenttype_detail.html"
    model = EquipmentType


class EquipmentTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "inventory.add_equipmenttype"
    template_name = "inventory/equipmenttype_form.html"
    model = EquipmentType
    form_class = EquipmentTypeForm
    success_url = reverse_lazy("inventory:equipmenttype_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next"] = self.request.GET.get("next") or self.request.POST.get("next") or ""
        return ctx

    def get_success_url(self):
        nxt = self.request.POST.get("next") or self.request.GET.get("next") or ""
        if nxt:
            # вернемся назад и подставим созданный тип в equipment_form
            return _append_query(nxt, equipment_type=self.object.pk)
        return super().get_success_url()


class EquipmentTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "inventory.change_equipmenttype"
    template_name = "inventory/equipmenttype_form.html"
    model = EquipmentType
    form_class = EquipmentTypeForm
    success_url = reverse_lazy("inventory:equipmenttype_list")


class EquipmentTypeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "inventory.delete_equipmenttype"
    template_name = "inventory/equipmenttype_confirm_delete.html"
    model = EquipmentType
    success_url = reverse_lazy("inventory:equipmenttype_list")

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, "Нельзя удалить тип: он используется в оборудовании.")
            return redirect("inventory:equipmenttype_detail", pk=self.object.pk)