from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("equipment/create/", views.EquipmentCreateView.as_view(), name="equipment_create"),
    path("equipment/<int:pk>/edit/", views.EquipmentUpdateView.as_view(), name="equipment_edit"),
    path("equipment/<int:pk>/move/", views.EquipmentMoveView.as_view(), name="equipment_move"),

    path("equipment/", views.EquipmentListView.as_view(), name="equipment_list"),
    path("equipment/<int:pk>/", views.EquipmentDetailView.as_view(), name="equipment_detail"),
    # path("equipment/print/", views.EquipmentPrintView.as_view(), name="equipment_print"),
    path("equipment/pdf/", views.EquipmentListPdfView.as_view(), name="equipment_list_pdf"),

    path("equipment/<int:pk>/qr.png", views.equipment_qr_png, name="equipment_qr_png"),
    path("equipment/<int:pk>/qr-label/", views.equipment_qr_label, name="equipment_qr_label"),

    path("documents/<int:pk>/", views.DocumentDetailView.as_view(), name="document_detail"),
    path("documents/<int:pk>/pdf/", views.DocumentPdfView.as_view(), name="document_pdf"),
    path("documents/<int:pk>/apply/", views.apply_document_view, name="document_apply"),

    path("ajax/employees/", views.EmployeesByOrganizationView.as_view(), name="ajax_employees_by_org"),

]