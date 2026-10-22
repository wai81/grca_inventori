from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import TemplateView

from .forms import LoginForm
from .profile import PERMISSION_ACTIONS, permission_table


class UserLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "users/profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["permission_actions"] = [label for _, label in PERMISSION_ACTIONS]
        ctx["permission_rows"] = permission_table(self.request.user)
        return ctx
