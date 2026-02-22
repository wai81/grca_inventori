from django.urls import path
from . import views

app_name = "directory"

urlpatterns = [


    path("employees/", views.EmployeeListView.as_view(), name="employee_list"),

    path("employees/pdf/", views.EmployeeListPdfView.as_view(), name="employee_list_pdf"),


]