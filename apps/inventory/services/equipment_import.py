import csv
import io

from django.db import transaction
from django.http import HttpResponse

from apps.directory.models import Organization
from apps.inventory.models import Equipment, EquipmentImportLog, EquipmentType

HEADER_ALIASES = {
    "organization": {
        "organization",
        "организация",
        "орг",
    },
    "device_type": {
        "device_type",
        "type",
        "тип",
        "тип_устройства",
        "вид",
    },
    "name": {
        "name",
        "наименование",
        "название",
    },
    "inventory_number": {
        "inventory_number",
        "inventory",
        "инвентарный_номер",
        "инвномер",
        "инв_номер",
    },
    "serial_number": {
        "serial_number",
        "serial",
        "серийный_номер",
        "серийник",
    },
    "status": {
        "status",
        "статус",
    },
    # "qr_token": {
    #     "qr_token",
    #     "qr",
    #     "qrтокен",
    #     "токен",
    # },
}

REQUIRED_COLUMNS = ("organization", "device_type", "name")


def normalize_header(value: str) -> str:
    value = (value or "").strip().lower()
    return "".join(ch for ch in value if ch.isalnum() or ch == "_")


def resolve_header(header: str):
    normalized = normalize_header(header)
    for canonical, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def decode_uploaded_file(uploaded_file) -> str:
    raw = uploaded_file.read()
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Не удалось прочитать CSV. Сохрани файл как UTF-8 или CP1251.")


def build_template_response():
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="equipment_import_template.csv"'
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";")
    writer.writerow([
        "Организация",
        "Тип",
        "Наименование",
        "Инвентарный номер",
        "Серийный номер",
        "Статус",
        # "QR токен",
    ])
    writer.writerow([
        "Главный офис",
        "Ноутбук",
        "Lenovo ThinkPad T14",
        "INV-001",
        "SN-001",
        "В эксплуатации",
        # "eq_001",
    ])
    return response


def parse_csv_preview(uploaded_file, delimiter=";", update_existing=True):
    text = decode_uploaded_file(uploaded_file)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    if not reader.fieldnames:
        raise ValueError("CSV-файл пустой или не содержит заголовков.")

    header_map = {}
    unknown_headers = []

    for header in reader.fieldnames:
        canonical = resolve_header(header)
        if canonical:
            header_map[header] = canonical
        else:
            unknown_headers.append(header)

    missing = [col for col in REQUIRED_COLUMNS if col not in header_map.values()]
    if missing:
        missing_verbose = {
            "organization": "Организация",
            "device_type": "Тип",
            "name": "Наименование",
        }
        raise ValueError(
            "Не хватает обязательных столбцов: "
            + ", ".join(missing_verbose.get(col, col) for col in missing)
        )

    rows = []

    for line_number, raw_row in enumerate(reader, start=2):
        data = {
            canonical: (raw_row.get(source_header) or "").strip()
            for source_header, canonical in header_map.items()
        }

        errors = []

        for required in REQUIRED_COLUMNS:
            if not data.get(required):
                errors.append(f"Пустое поле: {required}")

        existing = None
        if update_existing and data.get("inventory_number"):
            existing = Equipment.objects.filter(
                inventory_number=data["inventory_number"]
            ).only("id").first()

        if errors:
            action = "skip"
        elif existing:
            action = "update"
        else:
            action = "create"

        rows.append({
            "line": line_number,
            "data": data,
            "action": action,
            "errors": errors,
        })

    return {
        "rows": rows,
        "unknown_headers": unknown_headers,
        "total_rows": len(rows),
    }




def import_preview_rows(rows, user=None, filename="import.csv", update_existing=True):
    log = EquipmentImportLog.objects.create(
        created_by=user if getattr(user, "is_authenticated", False) else None,
        filename=filename,
        total_rows=len(rows),
        status="success",
    )

    created_count = 0
    updated_count = 0
    skipped_count = 0
    details = []

    try:
        with transaction.atomic():
            for row in rows:
                line = row["line"]
                data = row["data"]
                errors = list(row.get("errors") or [])

                if errors:
                    skipped_count += 1
                    details.append({
                        "line": line,
                        "result": "skipped",
                        "errors": errors,
                    })
                    continue

                organization, _ = Organization.objects.get_or_create(
                    name=data["organization"]
                )
                equipment_type, _ = EquipmentType.objects.get_or_create(
                    name=data["equipment_type"]
                )

                equipment = None
                if update_existing and data.get("inventory_number"):
                    equipment = Equipment.objects.filter(
                        inventory_number=data["inventory_number"]
                    ).first()

                is_create = equipment is None
                if is_create:
                    equipment = Equipment()
                    created_count += 1
                else:
                    updated_count += 1

                equipment.organization = organization
                equipment.equipment_type = equipment_type
                equipment.name = data["name"]

                if data.get("inventory_number"):
                    equipment.inventory_number = data["inventory_number"]

                if data.get("serial_number"):
                    equipment.serial_number = data["serial_number"]

                if data.get("status"):
                    equipment.status = data["status"]

                # if data.get("qr_token"):
                #     equipment.qr_token = data["qr_token"]

                equipment.save()

                details.append({
                    "line": line,
                    "result": "created" if is_create else "updated",
                    "inventory_number": data.get("inventory_number", ""),
                    "name": data.get("name", ""),
                })

    except Exception as exc:
        log.status = "failed"
        log.created_count = created_count
        log.updated_count = updated_count
        log.skipped_count = skipped_count
        details.append({"result": "error", "message": str(exc)})
        log.details = details
        log.save()
        raise

    log.created_count = created_count
    log.updated_count = updated_count
    log.skipped_count = skipped_count
    log.status = "partial" if skipped_count else "success"
    log.details = details
    log.save()

    return log