from django.contrib.auth import views as auth_views
from django.urls import path, include
from apps.users.forms import LoginForm

urlpatterns = [
    path("users/login/", auth_views.LoginView.as_view(
        template_name="login.html",
        authentication_form=LoginForm
    ), name="login"),

    path("users/", include("django.contrib.auth.urls")),
]