"""
URL configuration for grca_inventori project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView, TemplateView

from config import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('color/', views.color, name='color'),
    path('typography/', views.typography, name='typography'),
    path('feather-icon/', views.icon_feather, name='icon_feather'),
    path('sample-page/', views.sample_page, name='sample_page'),
    path('accounts/', include("django.contrib.auth.urls")),
    # path('', views.home, name='home'),
    path('', RedirectView.as_view(pattern_name="inventory:equipment_list", permanent=False), name="index"),
    path('', include("inventory.urls")),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

