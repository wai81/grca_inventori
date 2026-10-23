"""Запоминание фильтра списка оборудования, чтобы после правки возвращаться к тому же списку."""
from django.urls import reverse

SESSION_KEY = "equipment_list_query"


def remember_equipment_list_query(request):
    """Сохраняет параметры фильтра и страницы текущего списка в сессии."""
    params = request.GET.copy()
    for key in list(params):
        values = [v for v in params.getlist(key) if v.strip()]
        if values:
            params.setlist(key, values)
        else:
            params.pop(key)
    query = params.urlencode()
    if request.session.get(SESSION_KEY, "") != query:
        request.session[SESSION_KEY] = query


def equipment_list_url(request):
    """Адрес списка оборудования с последним применённым фильтром."""
    url = reverse("inventory:equipment_list")
    session = getattr(request, "session", None)
    query = session.get(SESSION_KEY, "") if session is not None else ""
    return f"{url}?{query}" if query else url


def equipment_list_context(request):
    """Context processor: {{ equipment_list_url }} для кнопок «Отмена» и хлебных крошек."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    return {"equipment_list_url": equipment_list_url(request)}
