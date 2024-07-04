"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
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
from django.urls import include
from django.urls import path

from . import settings
from . import views
from .views import dashboard
from .views import register
from .views import user_login
from .views import user_logout


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.core),
    path("admin_panel/", include("admins.urls", namespace="admin_panel")),
    path("register/", register, name="register"),
    path("login/", user_login, name="login"),
    path("dashboard/", dashboard, name="dashboard"),
    path("logout/", user_logout, name="logout"),
    path('annotate/<int:project_id>/', views.annotate_sentence, name='annotate_sentence'),
    path('save_annotations/', views.save_annotations, name='save_annotations'),
    path('get_annotation/<int:sentence_id>/', views.get_annotation, name='get_annotation'),
]

# Additional settings for development
if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += [path("__debug__", include("debug_toolbar.urls"))]

