from django.urls import path

from . import manage_views as views

app_name = "users"

urlpatterns = [
    path("", views.UserListView.as_view(), name="user_list"),
    path("create/", views.UserCreateView.as_view(), name="user_create"),
    path("<int:pk>/", views.UserUpdateView.as_view(), name="user_edit"),
    path("<int:pk>/password/", views.UserSetPasswordView.as_view(), name="user_password"),
    path("<int:pk>/toggle-active/", views.UserToggleActiveView.as_view(), name="user_toggle_active"),
    path("roles/", views.RoleListView.as_view(), name="role_list"),
    path("roles/create/", views.RoleFormView.as_view(), name="role_create"),
    path("roles/<int:pk>/", views.RoleFormView.as_view(), name="role_edit"),
    path("roles/<int:pk>/delete/", views.RoleDeleteView.as_view(), name="role_delete"),
]
