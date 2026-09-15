from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [\
    # Projets principaux
    path('nouveau/', views.project_create_view, name='project_create'),
    path('<slug:slug>/', views.project_detail_view, name='project_detail'),
    path('<slug:slug>/parametres/', views.project_edit_view, name='project_edit'),
    
    # Sous-projets
    path('<slug:project_slug>/sous-projets/nouveau/', views.subproject_create_view, name='subproject_create'),
    path('<slug:project_slug>/<slug:subproject_slug>/', views.subproject_detail_view, name='subproject_detail'),
    
    # Tâches (dans le sous-projet)
    path('<slug:project_slug>/<slug:subproject_slug>/tasks/create/', views.task_create_view, name='task_create'),
    path('tasks/<int:task_id>/move/', views.task_move_view, name='task_move'),
    path('tasks/<int:task_id>/delete/', views.task_delete_view, name='task_delete'),
    
    # Mots de passe / Accès (dans le sous-projet)
    path('<slug:project_slug>/<slug:subproject_slug>/credentials/create/', views.credential_create_view, name='credential_create'),
    path('credentials/<int:credential_id>/delete/', views.credential_delete_view, name='credential_delete'),

    # Documents & Fichiers (Projet & Sous-projet)
    path('<slug:project_slug>/resources/create/', views.resource_create_view, name='project_resource_create'),
    path('<slug:project_slug>/<slug:subproject_slug>/resources/create/', views.resource_create_view, name='subproject_resource_create'),
    path('resources/<int:resource_id>/delete/', views.resource_delete_view, name='resource_delete'),
]
