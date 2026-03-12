from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from apps.inventory.form import EquipmentCSVImportForm
from apps.inventory.models import Equipment, EquipmentImportLog
from apps.inventory.services.equipment_import import (
    build_template_response,
    import_preview_rows,
    parse_csv_preview,
)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    change_list_template = "admin/inventory/equipment/change_list.html"
    list_display = ("id", "name", "inventory_number", "organization", "equipment_type")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-csv/",
                self.admin_site.admin_view(self.import_csv_view),
                name="inventory_equipment_import_csv",
            ),
            path(
                "import-csv/confirm/",
                self.admin_site.admin_view(self.confirm_import_csv_view),
                name="inventory_equipment_import_csv_confirm",
            ),
            path(
                "download-csv-template/",
                self.admin_site.admin_view(self.download_template_view),
                name="inventory_equipment_download_csv_template",
            ),
        ]
        return custom_urls + urls

    def download_template_view(self, request):
        return build_template_response()

    def import_csv_view(self, request):
        if request.method == "POST":
            form = EquipmentCSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                uploaded_file = form.cleaned_data["csv_file"]
                delimiter = form.cleaned_data["delimiter"]
                update_existing = form.cleaned_data["update_existing"]

                try:
                    preview = parse_csv_preview(
                        uploaded_file=uploaded_file,
                        delimiter=delimiter,
                        update_existing=update_existing,
                    )
                except Exception as exc:
                    messages.error(request, f"Ошибка разбора CSV: {exc}")
                    return redirect("..")

                request.session["equipment_csv_preview_rows"] = preview["rows"]
                request.session["equipment_csv_preview_meta"] = {
                    "filename": uploaded_file.name,
                    "delimiter": delimiter,
                    "update_existing": update_existing,
                }

                context = {
                    **self.admin_site.each_context(request),
                    "opts": self.model._meta,
                    "title": "Предпросмотр импорта CSV",
                    "preview": preview,
                    "meta": request.session["equipment_csv_preview_meta"],
                }
                return TemplateResponse(
                    request,
                    "admin/inventory/equipment/csv_preview.html",
                    context,
                )
        else:
            form = EquipmentCSVImportForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Импорт оборудования из CSV",
            "form": form,
        }
        return TemplateResponse(
            request,
            "admin/inventory/equipment/csv_import.html",
            context,
        )

    def confirm_import_csv_view(self, request):
        if request.method != "POST":
            return redirect("admin:inventory_equipment_import_csv")

        rows = request.session.get("equipment_csv_preview_rows")
        meta = request.session.get("equipment_csv_preview_meta")

        if not rows or not meta:
            messages.error(request, "Нет данных для импорта. Сначала загрузите CSV.")
            return redirect("admin:inventory_equipment_import_csv")

        log = import_preview_rows(
            rows=rows,
            user=request.user,
            filename=meta.get("filename", "import.csv"),
            update_existing=meta.get("update_existing", True),
        )

        request.session.pop("equipment_csv_preview_rows", None)
        request.session.pop("equipment_csv_preview_meta", None)

        if log.status == "success":
            messages.success(
                request,
                f"Импорт завершён: создано {log.created_count}, обновлено {log.updated_count}.",
            )
        elif log.status == "partial":
            messages.warning(
                request,
                f"Импорт завершён частично: создано {log.created_count}, "
                f"обновлено {log.updated_count}, пропущено {log.skipped_count}.",
            )
        else:
            messages.error(request, "Импорт завершился с ошибкой.")

        return redirect(reverse("admin:inventory_equipmentimportlog_changelist"))


@admin.register(EquipmentImportLog)
class EquipmentImportLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "filename",
        "created_by",
        "status",
        "total_rows",
        "created_count",
        "updated_count",
        "skipped_count",
    )
    readonly_fields = (
        "created_at",
        "created_by",
        "filename",
        "status",
        "total_rows",
        "created_count",
        "updated_count",
        "skipped_count",
        "details",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False