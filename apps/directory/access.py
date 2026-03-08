from .models import Organization


def get_allowed_organizations(user):
    if user.is_superuser:
        return Organization.objects.all()

    access = getattr(user, "organization_access", None)
    if not access:
        return Organization.objects.none()

    return access.organizations.all()


def filter_queryset_by_user_orgs(qs, user, field_name="organization"):
    if user.is_superuser:
        return qs

    allowed_ids = get_allowed_organizations(user).values_list("id", flat=True)
    return qs.filter(**{f"{field_name}__in": allowed_ids}).distinct()


def user_has_org_access(user, organization_id):
    if user.is_superuser:
        return True

    access = getattr(user, "organization_access", None)
    if not access:
        return False

    return access.organizations.filter(pk=organization_id).exists()