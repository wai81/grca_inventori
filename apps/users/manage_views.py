"""Управление пользователями и их правами из приложения (только для суперпользователя)."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView

from apps.directory.access import safe_next_url
from apps.directory.models import Organization

from .manage_forms import RoleForm, UserCreateForm, UserManageForm, UserSetPasswordForm, user_role
from .models import User
from .profile import PERMISSION_ACTIONS, initials
from .role_utils import is_system, ordered_roles, permission_rows, role_cards, role_css, role_label


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        # гостя — на вход, остальным — 403
        self.raise_exception = self.request.user.is_authenticated
        return super().handle_no_permission()


def _users_queryset():
    return User.objects.prefetch_related(
        "groups",
        "organization_access__organizations",
    ).order_by("-is_active", "last_name", "first_name", "username")


def _decorate(user):
    """Роль и организации пользователя для списка и карточки."""
    user.role_name = user_role(user)
    user.initials = initials(user)
    if user.is_superuser:
        user.role_label, user.role_css = "Суперпользователь", "superuser"
    else:
        user.role_label = role_label(user.role_name) if user.role_name else "Без роли"
        user.role_css = role_css(user.role_name)
    access = getattr(user, "organization_access", None)
    user.org_list = sorted(access.organizations.all(), key=lambda o: o.code) if access else []
    return user


class UserListView(SuperuserRequiredMixin, ListView):
    template_name = "users/manage/user_list.html"
    paginate_by = 25
    context_object_name = "users"

    def get_queryset(self):
        qs = _users_queryset()
        g = self.request.GET
        q = (g.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) |
                           Q(last_name__icontains=q) | Q(email__icontains=q))
        role = g.get("role")
        if role == "superuser":
            qs = qs.filter(is_superuser=True)
        elif role == "none":
            qs = qs.filter(is_superuser=False, groups__isnull=True)
        elif role:
            qs = qs.filter(is_superuser=False, groups__name=role)
        org = g.get("organization")
        if org and org.isdigit():
            qs = qs.filter(Q(is_superuser=True) | Q(organization_access__organizations=org))
        active = g.get("active")
        if active in ("1", "0"):
            qs = qs.filter(is_active=active == "1")
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for u in ctx["users"]:
            _decorate(u)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        ctx["role_choices"] = [("superuser", "Суперпользователь")] + \
            [(g.name, role_label(g.name)) for g in ordered_roles()] + [("none", "Без роли")]
        ctx["organizations"] = Organization.objects.order_by("code")
        ctx["total_count"] = User.objects.count()
        ctx["no_access_count"] = User.objects.filter(is_active=True, is_superuser=False).filter(
            Q(groups__isnull=True) | Q(organization_access__isnull=True) |
            Q(organization_access__organizations__isnull=True)).distinct().count()
        return ctx


class UserFormMixin(SuperuserRequiredMixin):
    template_name = "users/manage/user_form.html"
    model = User

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["current_user"] = self.request.user
        return kw

    def get_success_url(self):
        return safe_next_url(self.request, self.request.POST.get("next"),
                             reverse("users:user_list"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next"] = safe_next_url(self.request, self.request.GET.get("next") or self.request.POST.get("next"))
        ctx["roles"] = role_cards(with_counts=False)
        return ctx


class UserCreateView(UserFormMixin, CreateView):
    form_class = UserCreateForm

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Пользователь «{self.object.username}» создан.")
        return response


class UserUpdateView(UserFormMixin, UpdateView):
    form_class = UserManageForm

    def get_queryset(self):
        return _users_queryset()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        _decorate(self.object)
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Изменения пользователя «{self.object.username}» сохранены.")
        return response


class UserSetPasswordView(SuperuserRequiredMixin, FormView):
    template_name = "users/manage/user_password.html"
    form_class = UserSetPasswordForm

    def dispatch(self, request, *args, **kwargs):
        self.target = get_object_or_404(User, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.target
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["target"] = self.target
        return ctx

    def form_valid(self, form):
        form.save()
        if self.target.pk == self.request.user.pk:
            # иначе после смены своего пароля сессия завершится
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(self.request, self.target)
        messages.success(self.request, f"Пароль пользователя «{self.target.username}» изменён.")
        return redirect("users:user_edit", pk=self.target.pk)


class UserToggleActiveView(SuperuserRequiredMixin, View):
    def post(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        back = safe_next_url(request, request.POST.get("next"), reverse("users:user_list"))
        if target.pk == request.user.pk:
            messages.error(request, "Нельзя заблокировать свою учётную запись.")
            return redirect(back)
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        if target.is_active:
            messages.success(request, f"Пользователь «{target.username}» разблокирован.")
        else:
            messages.success(request, f"Пользователь «{target.username}» заблокирован — вход запрещён.")
        return redirect(back)


class RoleListView(SuperuserRequiredMixin, TemplateView):
    template_name = "users/manage/role_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["roles"] = role_cards()
        return ctx

    def post(self, request):
        """Восстановить стандартные права системных ролей (свои роли не меняются)."""
        from apps.inventory.roles import bootstrap_roles
        bootstrap_roles()
        messages.success(request, "Права системных ролей восстановлены по умолчанию.")
        return redirect("users:role_list")


class RoleFormView(SuperuserRequiredMixin, FormView):
    template_name = "users/manage/role_form.html"
    form_class = RoleForm

    def dispatch(self, request, *args, **kwargs):
        self.group = get_object_or_404(Group, pk=kwargs["pk"]) if "pk" in kwargs else None
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        source = self.group
        if source is None and (self.request.GET.get("copy") or "").isdigit():
            source = Group.objects.filter(pk=self.request.GET["copy"]).first()  # новая роль копией существующей
        kw["group"] = self.group
        kw["initial_rows"] = permission_rows(source)
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx["form"]
        ctx["group"] = self.group
        ctx["system"] = bool(self.group and is_system(self.group))
        ctx["permission_actions"] = PERMISSION_ACTIONS
        # строки матрицы с привязанными полями формы
        ctx["matrix"] = [{
            "title": row["title"],
            "cells": [{**cell, "field": form[cell["name"]]} for cell in row["cells"]],
        } for row in permission_rows(None)]
        if self.group:
            ctx["role_users"] = self.group.user_set.order_by("last_name", "first_name", "username")
        return ctx

    def form_valid(self, form):
        group = form.save()
        verb = "сохранена" if self.group else "создана"
        messages.success(self.request, f"Роль «{role_label(group.name)}» {verb}.")
        return redirect("users:role_list")


class RoleDeleteView(SuperuserRequiredMixin, View):
    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)
        if is_system(group):
            messages.error(request, "Системную роль удалить нельзя.")
            return redirect("users:role_edit", pk=pk)
        count = group.user_set.count()
        name = group.name
        group.delete()
        tail = f" У {count} пользовател{'я' if count == 1 else 'ей'} больше нет роли." if count else ""
        messages.success(request, f"Роль «{name}» удалена.{tail}")
        return redirect("users:role_list")
