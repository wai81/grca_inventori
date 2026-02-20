from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("equipment/", views.EquipmentListView.as_view(), name="equipment_list"),
    # path("equipment/print/", views.EquipmentPrintView.as_view(), name="equipment_print"),
    path("equipment/pdf/", views.EquipmentListPdfView.as_view(), name="equipment_list_pdf"),
    path("equipment/<int:pk>/", views.EquipmentDetailView.as_view(), name="equipment_detail"),
    path("equipment/<int:pk>/qr.png", views.equipment_qr_png, name="equipment_qr_png"),
    path("equipment/<int:pk>/qr-label/", views.equipment_qr_label, name="equipment_qr_label"),

    path("employees/", views.EmployeeListView.as_view(), name="employee_list"),
    # path("employees/print/", views.EmployeePrintView.as_view(), name="employee_print"),
    path("employees/pdf/", views.EmployeeListPdfView.as_view(), name="employee_list_pdf"),

    path("documents/<int:pk>/", views.DocumentDetailView.as_view(), name="document_detail"),
    path("documents/<int:pk>/pdf/", views.DocumentPdfView.as_view(), name="document_pdf"),
    path("documents/<int:pk>/apply/", views.apply_document_view, name="document_apply"),

    # примитивные действия (лучше позже заменить на формы):
    # path("equipment/<int:pk>/assign/<int:employee_id>/", views.assign_equipment, name="assign_equipment"),
    # path("equipment/<int:pk>/unassign/", views.assign_equipment, {"employee_id": None}, name="unassign_equipment"),
    # path("equipment/<int:pk>/status/<str:status>/", views.set_status, name="set_status"),
]