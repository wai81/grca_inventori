from io import BytesIO
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView
from django_filters.views import FilterView

from inventory.filters import EmployeeFilter, EquipmentFilter
from inventory.models import InventoryDocument, Equipment, Employee
from inventory.pdf import render_pdf_response
from inventory.services import apply_document


class EquipmentListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    permission_required = "inventory.view_equipment"
    template_name = "inventory/equipment_list.html"
    model = Equipment
    filterset_class = EquipmentFilter
    paginate_by = 25

    def get_queryset(self):
        return Equipment.objects.select_related("organization", "equipment_type", "assigned_to", "assigned_to__department")


class EquipmentListPdfView(EquipmentListView):
    permission_required = "inventory.view_equipment"

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        filt = self.get_filterset(self.filterset_class)
        context = {"filter": filt, "request": request}
        return render_pdf_response(request, "inventory/pdf/equipment_list_pdf.html", context, "equipment.pdf")


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
    return HttpResponse(
        request.render_to_response("inventory/equipment_qr_label.html", {"object": equipment}).content
    )


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