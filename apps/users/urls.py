from django.contrib.auth import views as auth_views
from django.urls import path, include
from apps.users.forms import LoginForm
from .views import UserLoginView

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),

    path("users/", include("django.contrib.auth.urls")),
]