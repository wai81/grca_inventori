from django.contrib.auth import views as auth_views
from django.urls import path, include
from accounts.forms import LoginForm

urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(
        template_name="login.html",
        authentication_form=LoginForm
    ), name="login"),

    path("accounts/", include("django.contrib.auth.urls")),
]