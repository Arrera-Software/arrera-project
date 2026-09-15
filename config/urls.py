"""
URL configuration for arrera-project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Administration Django (restreinte aux superutilisateurs)
    path('admin/', admin.site.urls),

    # Authentification & Dashboard
    path('', include('accounts.urls')),

    # Gestion de projets & Kanban
    path('projets/', include('projects.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
