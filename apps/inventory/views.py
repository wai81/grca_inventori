import csv
import io
from datetime import datetime
from io import BytesIO
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import ProtectedError, Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import DetailView, UpdateView, FormView, CreateView, DeleteView, ListView
from django_filters.views import FilterView

from apps.directory.models import Employee, Organization
from apps.inventory.filters import EquipmentFilter
from apps.inventory.form import (
    EquipmentForm, EquipmentMoveForm, EquipmentTypeForm, EquipmentCSVImportForm)
from apps.inventory.models import (
    InventoryDocument, Equipment, EquipmentEventType,
    EquipmentEvent, EquipmentType, EquipmentStatus, PrintMode)
from django.conf import settings
from config.pdf import render_pdf_response

from apps.directory.access import filter_queryset_by_user_orgs, user_has_org_access



class EquipmentListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    permission_required = "inventory.view_equipment"
    template_name = "inventory/equipment_list.html"
    model = Equipment
    filterset_class = EquipmentFilter
    paginate_by = 10

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["equipmenttype_meta"] = list(EquipmentType.objects.values("id", "category"))
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx

    def get_queryset(self):
        qs = Equipment.objects.select_related(
            "organization", "equipment_type", "assigned_to", "assigned_to__department"
        ).order_by('-created_at')
        return filter_queryset_by_user_orgs(qs, self.request.user, "organization")


class EquipmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "inventory.change_equipment"
    model = Equipment
    form_class = EquipmentForm
    template_name = "inventory/equipment_form.html"
    success_url = reverse_lazy("inventory:equipment_list")

    def get_queryset(self):
        qs = Equipment.objects.select_related(
            "organization", "equipment_type", "assigned_to", "assigned_to__department"
        )
        return filter_queryset_by_user_orgs(qs, self.request.user, "organization")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["equipmenttype_meta"] = list(EquipmentType.objects.values("id", "category"))
        return ctx


class EquipmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "inventory.add_equipment"
    model = Equipment
    form_class = EquipmentForm
    template_name = "inventory/equipment_form.html"
    success_url = reverse_lazy("inventory:equipment_list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

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


class EquipmentMoveView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "inventory.change_equipment"
    template_name = "inventory/equipment_move_form.html"
    form_class = EquipmentMoveForm

    def dispatch(self, request, *args, **kwargs):
        qs = Equipment.objects.select_related("organization", "assigned_to")
        qs = filter_queryset_by_user_orgs(qs, request.user, "organization")
        self.equipment = get_object_or_404(qs, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        ini = super().get_initial()

        # предзаполнение "снять закрепление" или "кому передать"
        if "to_employee" in self.request.GET:
            raw = self.request.GET.get("to_employee", "")
            ini["to_employee"] = None if raw == "" else raw

        return ini

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["equipment"] = self.equipment
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.equipment
        ctx["next"] = self.request.GET.get("next") or self.request.POST.get("next") or ""
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

        next_url = (self.request.POST.get("next") or "").strip()
        if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={self.request.get_host()},
                require_https=self.request.is_secure(),
        ):
            return redirect(next_url)

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
        qs = Equipment.objects.select_related(
            "organization", "equipment_type", "assigned_to", "assigned_to__department"
        ).prefetch_related("events")
        return filter_queryset_by_user_orgs(qs, self.request.user, "organization")


class DocumentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "inventory.view_inventorydocument"
    template_name = "inventory/document_detail.html"
    model = InventoryDocument

    def get_queryset(self):
        qs = InventoryDocument.objects.select_related(
            "organization", "from_employee", "to_employee"
        ).prefetch_related("lines", "lines__equipment")
        # return InventoryDocument.objects.select_related("organization", "from_employee", "to_employee").prefetch_related("lines", "lines__equipment")
        return filter_queryset_by_user_orgs(qs, self.request.user, "organization")


class DocumentPdfView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "inventory.view_inventorydocument"
    model = InventoryDocument

    def get_queryset(self):
        qs = InventoryDocument.objects.select_related(
            "organization", "from_employee", "to_employee"
        ).prefetch_related("lines", "lines__equipment")
        # return InventoryDocument.objects.select_related("organization", "from_employee", "to_employee").prefetch_related("lines")
        return filter_queryset_by_user_orgs(qs, self.request.user, "organization")

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

        if not user_has_org_access(request.user, org_id):
            return JsonResponse({"results": []})

        q = (request.GET.get("q") or "").strip()

        qs = (
            Employee.objects.filter(
                organization_id=org_id,
                active=True
            )
            .select_related("department")
            .order_by("full_name")
        )


        if q:
            qs = qs.filter(full_name__icontains=q)

        data = [
            {"id": e.id, "name": e.full_name,  "department": (e.department.name if e.department else "")}
            for e in qs[:200]
        ]
        return JsonResponse({"results": data})


@login_required
@permission_required("inventory.view_equipment", raise_exception=True)
def equipment_qr_png(request, pk: int):
    equipment = get_object_or_404(
        filter_queryset_by_user_orgs(
            Equipment.objects.select_related("organization"),
            request.user,
            "organization",
        ),
        pk=pk,
    )
    # url = request.build_absolute_uri(reverse("inventory:equipment_detail", args=[equipment.pk]))
    url = f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={equipment.qr_token}"
    import qrcode
    img = qrcode.make(url)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")

@login_required
@permission_required("inventory.view_equipment", raise_exception=True)
def equipment_qr_label(request, pk: int):
    equipment = get_object_or_404(
        filter_queryset_by_user_orgs(
            Equipment.objects.select_related("organization", "assigned_to", "assigned_to__department"),
            request.user,
            "organization",
        ),
        pk=pk,
    )
    return render(request, "inventory/equipment_qr_label_58x40.html", {"object": equipment})

@login_required
@permission_required("inventory.change_inventorydocument", raise_exception=True)
def apply_document_view(request, pk: int):
    doc = get_object_or_404(
        filter_queryset_by_user_orgs(
            InventoryDocument.objects.select_related("organization"),
            request.user,
            "organization",
        ),
        pk=pk,
    )
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

class EquipmentImportCsvView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "inventory.add_equipment"
    template_name = "inventory/equipment_import_csv.html"
    form_class = EquipmentCSVImportForm
    success_url = reverse_lazy("inventory:equipment_list")

    required_columns = {"organization_code", "equipment_type", "name"}

    header_aliases = {
        "organization_code": {
            "organization_code",
            "org_code",
            "код_организации",
            "Код организации",
            "код",
            "organization",
            "организация",
        },
        "inventory_number": {
            "inventory_number",
            "инвентарный номер",
            "инв_номер",
            "инв. №",
            "инв №",
        },
        "name": {
            "name",
            "наименование",
            "название",
        },
        "assigned_to": {
            "assigned_to",
            "закреплено",
            "сотрудник",
            "ответственный",
            "фио",
        },
        "equipment_type": {
            "equipment_type",
            "тип",
            "тип оборудования",
            "вид оборудования",
        },
        "serial_number": {
            "serial_number",
            "серийный номер",
            "серийник",
        },
        "model": {
            "model",
            "модель",
        },
        "specs": {
            "specs",
            "характеристики",
            "описание",
        },
        "cpu": {
            "cpu",
            "процессор",
        },
        "ram_gb": {
            "ram_gb",
            "озу",
            "озу гб",
            "ram",
            "ram gb",
        },
        "storageHDD_gb": {
            "storagehdd_gb",
            "hdd",
            "hdd гб",
        },
        "storageSDD_gb": {
            "storagesdd_gb",
            "sdd",
            "ssd",
            "ssd гб",
            "sdd гб",
        },
        "print_format": {
            "print_format",
            "формат печати",
        },
        "print_mode": {
            "print_mode",
            "тип печати",
            "печать",
        },
        "status": {
            "status",
            "статус",
        },
        "commissioning_date": {
            "commissioning_date",
            "дата поступления",
            "дата ввода",
        },
    }

    def _normalize_header(self, value):
        return " ".join((value or "").strip().lower().replace("_", " ").split())

    def _map_row_keys(self, row):
        mapped = {}
        for raw_key, value in row.items():
            if not raw_key:
                continue
            normalized = self._normalize_header(raw_key)

            canonical = None
            for field_name, aliases in self.header_aliases.items():
                normalized_aliases = {self._normalize_header(a) for a in aliases}
                if normalized in normalized_aliases:
                    canonical = field_name
                    break

            if canonical:
                mapped[canonical] = (value or "").strip()

        return mapped

    def _parse_int(self, value):
        value = (value or "").strip()
        if not value:
            return None
        return int(value)

    def _parse_date(self, value):
        value = (value or "").strip()
        if not value:
            return None

        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        raise ValueError(f"Неверная дата: {value}")

    def _build_choice_map(self, choices):
        result = {}
        for code, label in choices:
            result[self._normalize_header(code)] = code
            result[self._normalize_header(label)] = code
        return result

    def form_valid(self, form):
        upload = form.cleaned_data["csv_file"]
        update_existing = form.cleaned_data.get("update_existing", False)
        delimiter = form.cleaned_data.get("delimiter", ";")
        raw = upload.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)


        if not reader.fieldnames:
            form.add_error("csv_file", "CSV файл пустой или не содержит заголовков.")
            return self.form_invalid(form)

        normalized_headers = set()

        for h in reader.fieldnames:
            if h:
                mapped_name = self._map_row_keys({h: ""}).keys()
                normalized_headers.update(mapped_name)

        missing = self.required_columns - normalized_headers
        if missing:
            human_names = {
                "organization_code": "Код организации",
                "equipment_type": "Тип",
                "name": "Наименование",
            }
            form.add_error(
                "csv_file",
                "Отсутствуют обязательные колонки: " + ", ".join(human_names[x] for x in sorted(missing))
            )
            return self.form_invalid(form)

        status_map = self._build_choice_map(EquipmentStatus.choices)
        print_mode_map = self._build_choice_map(PrintMode.choices)

        created_count = 0
        updated_count = 0
        errors = []

        for row_number, row in enumerate(reader, start=2):
            try:
                row = self._map_row_keys(row)

                if not any(row.values()):
                    continue

                org_code = row.get("organization_code", "")
                type_name = row.get("equipment_type", "")
                name = row.get("name", "")

                if not org_code or not type_name or not name:
                    raise ValueError("Обязательные поля: Код организации, Тип, Наименование")

                organization = Organization.objects.filter(code__iexact=org_code).first()
                if not organization:
                    raise ValueError(f"Организация не найдена по коду: {org_code}")

                if not user_has_org_access(self.request.user, organization.id):
                    raise ValueError(f"Нет доступа к организации: {org_code}")

                equipment_type = EquipmentType.objects.filter(name__iexact=type_name).first()
                if not equipment_type:
                    raise ValueError(f"Тип оборудования не найден: {type_name}")

                assigned_to = None
                assigned_name = row.get("assigned_to", "")
                if assigned_name:
                    assigned_to = Employee.objects.filter(
                        organization=organization,
                        full_name__iexact=assigned_name,
                        active=True,
                    ).first()
                    if not assigned_to:
                        raise ValueError(f"Сотрудник не найден: {assigned_name}")

                inventory_number = row.get("inventory_number", "")
                serial_number = row.get("serial_number", "")

                equipment = None
                action = "create"

                if update_existing:
                    if inventory_number:
                        equipment = Equipment.objects.filter(
                            organization=organization,
                            inventory_number=inventory_number
                        ).first()
                    elif serial_number:
                        equipment = Equipment.objects.filter(
                            organization=organization,
                            serial_number=serial_number
                        ).first()

                    if equipment:
                        action = "update"

                if not equipment:
                    equipment = Equipment(organization=organization)

                status_value = row.get("status", "")
                if status_value:
                    status_value = status_map.get(self._normalize_header(status_value))
                    if not status_value:
                        raise ValueError(f"Неизвестный статус: {row.get('status')}")
                else:
                    status_value = EquipmentStatus.IN_USE

                print_mode_value = row.get("print_mode", "")
                if print_mode_value:
                    print_mode_value = print_mode_map.get(self._normalize_header(print_mode_value))
                    if not print_mode_value:
                        raise ValueError(f"Неизвестный тип печати: {row.get('print_mode')}")
                else:
                    print_mode_value = ""

                equipment.organization = organization
                equipment.equipment_type = equipment_type
                equipment.name = name
                equipment.inventory_number = inventory_number
                equipment.serial_number = row.get("serial_number", "")
                equipment.model = row.get("model", "")
                equipment.specs = row.get("specs", "")
                equipment.commissioning_date = self._parse_date(row.get("commissioning_date", ""))
                equipment.status = status_value
                equipment.assigned_to = assigned_to
                equipment.cpu = row.get("cpu", "")
                equipment.ram_gb = self._parse_int(row.get("ram_gb", ""))
                equipment.storageHDD_gb = self._parse_int(row.get("storageHDD_gb", ""))
                equipment.storageSDD_gb = self._parse_int(row.get("storageSDD_gb", ""))
                equipment.print_format = row.get("print_format", "")
                equipment.print_mode = print_mode_value

                equipment.save()

                if action == "create":
                    created_count += 1
                else:
                    updated_count += 1

            except Exception as e:
                errors.append(f"Строка {row_number}: {e}")

        if errors:
            messages.warning(
                self.request,
                f"Импорт завершён с ошибками. Создано: {created_count}, обновлено: {updated_count}, ошибок: {len(errors)}"
            )
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    import_errors=errors,
                    created_count=created_count,
                    updated_count=updated_count,
                )
            )

        messages.success(
            self.request,
            f"Импорт выполнен успешно. Создано: {created_count}, обновлено: {updated_count}"
        )
        return super().form_valid(form)


@login_required
@permission_required("inventory.add_equipment", raise_exception=True)
def equipment_csv_template(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="equipment_import_template_ru.csv"'
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";")
    writer.writerow([
        "Код организации",
        "Инвентарный номер",
        "Наименование",
        "Сотрудник",
        "Тип",
        "Серийный номер",
        "Модель",
        "Характеристики",
        "Процессор",
        "ОЗУ",
        "HDD",
        "SSD",
        "Формат печати",
        "Тип печати",
        "Статус",
        "Дата поступления",
    ])
    writer.writerow([
        "400",
        "INV-001",
        "Lenovo ThinkPad T14",
        "Иванов Иван Иванович",
        "Ноутбук",
        "SN123",
        "T14",
        "Core i5, 16GB RAM",
        "Intel Core i5",
        "16",
        "512",
        "",
        "A4",
        "Монохромная",
        "используется",
        "2024-01-10",

    ])
    return response
