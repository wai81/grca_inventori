from django.contrib.auth.views import LoginView
from django.shortcuts import render

from .forms import LoginForm


# Create your views here.

class UserLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True