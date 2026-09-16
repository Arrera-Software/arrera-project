"""
URL configuration for arrera-project.
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

urlpatterns = [
    # Administration Django (restreinte aux superutilisateurs)
    path('admin/', admin.site.urls),

    # Authentification & Dashboard
    path('', include('accounts.urls')),

    # Gestion de projets & Kanban
    path('projets/', include('projects.urls')),

    # Distribution des médias téléversés (fichiers, images, pièces jointes)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
