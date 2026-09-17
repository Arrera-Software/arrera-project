import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import Project, SubProject, KanbanColumn, Task, ProjectCredential, ProjectResource
from .forms import ProjectForm, SubProjectForm, TaskForm, ProjectCredentialForm, ProjectResourceForm

User = get_user_model()

# Journal dédié aux accès aux secrets du coffre-fort.
credential_logger = logging.getLogger('projects.credentials')


def ensure_subproject_columns(subproject):
    """Garantit l'existence des 4 colonnes standard dans le bon ordre."""
    standard_cols = [
        ("En attente", 1),
        ("À faire", 2),
        ("En cours", 3),
        ("Terminé", 4),
    ]
    for name, order in standard_cols:
        col = subproject.columns.filter(name__iexact=name).first()
        if not col:
            KanbanColumn.objects.create(subproject=subproject, name=name, order=order)
        elif col.order != order:
            col.order = order
            col.save(update_fields=['order'])


def check_project_access(user, project):
    """
    Vérifie si l'utilisateur a le droit d'accéder au projet.
    - Superutilisateur (Admin) : OUI
    - Chef de projet assigné : OUI
    - Membre assigné au projet : OUI
    - Autre utilisateur : NON
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if project.manager_id == user.id:
        return True
    if project.members.filter(id=user.id).exists():
        return True
    return False


def is_project_manager_or_admin(user, project):
    """Vérifie si l'utilisateur est administrateur ou chef de ce projet (tous les droits de gestion et suppression)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if project.manager_id == user.id:
        return True
    return False


@login_required
def project_create_view(request):
    """Création d'un nouveau projet (réservé exclusivement à l'administrateur superutilisateur)."""
    if not request.user.is_superuser:
        raise PermissionDenied("Seul l'administrateur système peut créer de nouveaux projets.")

    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            form.save_m2m()

            messages.success(request, f"Projet « {project.name} » créé avec succès.")
            return redirect('projects:project_detail', slug=project.slug)
    else:
        form = ProjectForm()

    return render(request, 'projects/project_form.html', {
        'form': form,
        'action_title': "Nouveau Projet",
        'button_label': "Créer le Projet",
        'is_edit': False,
    })


@login_required
def project_edit_view(request, slug):
    """Modification d'un projet existant (chef de projet ou admin)."""
    project = get_object_or_404(Project, slug=slug)
    if not is_project_manager_or_admin(request.user, project):
        raise PermissionDenied("Seul le chef de projet ou l'administrateur a l'autorisation de modifier ce projet.")

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, f"Projet « {project.name} » mis à jour avec succès.")
            return redirect('projects:project_detail', slug=project.slug)
    else:
        form = ProjectForm(instance=project)

    return render(request, 'projects/project_form.html', {
        'form': form,
        'project': project,
        'action_title': f"Paramètres de {project.name}",
        'button_label': "Enregistrer les modifications",
        'is_edit': True,
    })


@login_required
@require_POST
def project_delete_view(request, slug):
    """
    Suppression définitive d'un projet complet.
    Strictement réservé à l'Administrateur système (superutilisateur).
    Nécessite une double validation (nom du projet saisi à l'identique).
    """
    if not request.user.is_superuser:
        raise PermissionDenied("Seul un administrateur système a l'autorisation de supprimer un projet complet.")

    project = get_object_or_404(Project, slug=slug)
    confirm_name = request.POST.get('confirm_project_name', '').strip()

    if confirm_name != project.name:
        messages.error(request, "La confirmation a échoué : le nom du projet saisi ne correspond pas exactement.")
        return redirect('projects:project_edit', slug=project.slug)

    project_name = project.name

    # Supprimer les fichiers physiques attachés à l'ensemble du projet
    for res in project.resources.all():
        if res.file:
            try:
                res.file.delete(save=False)
            except Exception:
                pass

    project.delete()
    messages.success(request, f"Le projet « {project_name} » et l'ensemble de ses données ont été définitivement supprimés.")
    return redirect('home')


@login_required
def project_detail_view(request, slug):
    """
    Vue principale d'un Projet avec onglets :
    1. Accueil (Sous-projets)
    2. Tâches (Tableau Kanban global de tous les sous-projets avec filtre Personnel / Tous)
    3. Fichiers (Documents & Fichiers du projet et sous-projets)

    """
    project = get_object_or_404(Project, slug=slug)
    if not check_project_access(request.user, project):
        raise PermissionDenied("Vous n'êtes pas affecté à ce projet.")

    subprojects = project.subprojects.prefetch_related('tasks', 'credentials', 'resources').all()
    subproject_form = SubProjectForm()
    resource_form = ProjectResourceForm()
    
    # Ressources globales du projet et de ses sous-projets
    project_resources = project.resources.filter(subproject__isnull=True)
    all_resources = project.resources.select_related('subproject').all()
    
    is_admin = is_project_manager_or_admin(request.user, project)

    # Récupération de l'ensemble des tâches de tous les sous-projets
    all_tasks = Task.objects.filter(column__subproject__project=project).select_related(
        'column__subproject', 'column', 'assigned_to', 'created_by'
    ).prefetch_related('dependencies').order_by('column__order', 'due_date', '-created_at')

    total_tasks_count = all_tasks.count()
    personal_tasks_count = all_tasks.filter(assigned_to=request.user).count()
    resources_count = all_resources.count()
    today = timezone.localdate()
    active_tab = request.GET.get('tab', 'home')

    # Regroupement des tâches dans les colonnes Kanban globales
    standard_column_names = ["En attente", "À faire", "En cours", "Terminé"]
    existing_column_names = list(
        KanbanColumn.objects.filter(subproject__project=project)
        .values_list('name', flat=True)
        .distinct()
    )

    ordered_column_names = []
    for std_name in standard_column_names:
        if any(std_name.lower() == c.lower() for c in existing_column_names):
            ordered_column_names.append(std_name)
    for col_name in existing_column_names:
        if not any(col_name.lower() == c.lower() for c in ordered_column_names):
            ordered_column_names.append(col_name)
    if not ordered_column_names:
        ordered_column_names = standard_column_names

    kanban_columns_data = []
    for col_name in ordered_column_names:
        col_tasks = [t for t in all_tasks if t.column.name.strip().lower() == col_name.strip().lower()]
        kanban_columns_data.append({
            'name': col_name,
            'tasks': col_tasks,
            'count': len(col_tasks),
        })

    # Données optimisées pour la vue Gantt globale du projet
    tasks_gantt_data = []
    for t in all_tasks:
        start_d = t.start_date or (t.due_date if t.due_date else today)
        due_d = t.due_date or start_d
        assigned_name = t.assigned_to.first_name if (t.assigned_to and t.assigned_to.first_name) else (t.assigned_to.username if t.assigned_to else "Non assigné")
        assigned_avatar = (t.assigned_to.first_name[0] if t.assigned_to and t.assigned_to.first_name else (t.assigned_to.username[0] if t.assigned_to else "?")).upper()

        dep_ids = list(t.dependencies.values_list('id', flat=True))

        tasks_gantt_data.append({
            'id': t.id,
            'title': t.title,
            'subproject_name': t.column.subproject.name,
            'subproject_slug': t.column.subproject.slug,
            'description': t.description or '',
            'column_id': t.column_id,
            'column_name': t.column.name,
            'priority': t.priority,
            'priority_display': t.get_priority_display(),
            'start_date': t.start_date.strftime('%Y-%m-%d') if t.start_date else '',
            'due_date': t.due_date.strftime('%Y-%m-%d') if t.due_date else '',
            'has_due_date': bool(t.due_date),
            'assigned_id': str(t.assigned_to_id) if t.assigned_to_id else '',
            'assigned_name': (t.assigned_to.full_name if t.assigned_to else "Non assigné"),
            'assigned_email': (t.assigned_to.email if t.assigned_to else ""),
            'assigned_avatar': assigned_avatar,
            'is_blocked': t.has_unmet_dependencies(),
            'dependencies': dep_ids,
        })

    return render(request, 'projects/project_detail.html', {
        'project': project,
        'subprojects': subprojects,
        'subproject_form': subproject_form,
        'resource_form': resource_form,
        'project_resources': project_resources,
        'all_resources': all_resources,
        'all_tasks': all_tasks,
        'kanban_columns_data': kanban_columns_data,
        'total_tasks_count': total_tasks_count,
        'personal_tasks_count': personal_tasks_count,
        'resources_count': resources_count,
        'today': today,
        'is_admin': is_admin,
        'active_tab': active_tab,
        'tasks_gantt_json': json.dumps(tasks_gantt_data),
    })


@login_required
@require_POST
def subproject_create_view(request, project_slug):
    """Création d'un nouveau sous-projet (admin ou chef de projet)."""
    project = get_object_or_404(Project, slug=project_slug)
    if not is_project_manager_or_admin(request.user, project):
        raise PermissionDenied("Seul l'administrateur ou le chef de projet peut créer des sous-projets.")

    form = SubProjectForm(request.POST)
    if form.is_valid():
        subproject = form.save(commit=False)
        subproject.project = project
        subproject.save()

        # Création des colonnes Kanban standard avec "En attente"
        ensure_subproject_columns(subproject)

        messages.success(request, f"Sous-projet « {subproject.name} » créé avec succès.")
        return redirect('projects:subproject_detail', project_slug=project.slug, subproject_slug=subproject.slug)
    else:
        messages.error(request, "Erreur lors de la création du sous-projet.")
        return redirect('projects:project_detail', slug=project.slug)


@login_required
def subproject_detail_view(request, project_slug, subproject_slug):
    """
    Page d'un Sous-Projet avec ses onglets :
    1. Général : Tableau Kanban de toutes les tâches
    2. Personnel : Tâches assignées à l'utilisateur connecté
    3. Gantt : Calendrier Timeline & Deadlines des tâches
    4. Documents & Fichiers : Fichiers uploadés et liens du sous-projet et projet parent
    5. Mots de passe : Coffre-fort des accès
    """
    project = get_object_or_404(Project, slug=project_slug)
    if not check_project_access(request.user, project):
        raise PermissionDenied("Vous n'êtes pas affecté à ce projet.")

    subproject = get_object_or_404(SubProject, project=project, slug=subproject_slug)
    
    # Garantir les 4 colonnes Kanban
    ensure_subproject_columns(subproject)

    columns = subproject.columns.prefetch_related('tasks__assigned_to', 'tasks__dependencies__column').order_by('order').all()

    is_admin = is_project_manager_or_admin(request.user, project)

    # Le coffre-fort n'est visible que par le chef de projet / administrateur.
    credentials = subproject.credentials.all() if is_admin else ProjectCredential.objects.none()

    # Documents
    subproject_resources = subproject.resources.all()
    parent_resources = project.resources.filter(subproject__isnull=True)

    task_form = TaskForm(subproject=subproject)
    credential_form = ProjectCredentialForm()
    resource_form = ProjectResourceForm()
    edit_subproject_form = SubProjectForm(instance=subproject)

    # Récupérer les utilisateurs éligibles pour l'assignation de tâche (hors superutilisateurs)
    manager_qs = User.objects.filter(id=project.manager_id, is_active=True, is_superuser=False) if project.manager_id else User.objects.none()
    assignable_users = (project.members.filter(is_active=True, is_superuser=False) | manager_qs).distinct().order_by('first_name', 'username')

    # Récupérer les sous-projets frères pour la navigation rapide
    sibling_subprojects = project.subprojects.all()

    # Compteurs pour les badges d'onglets
    all_sub_tasks = Task.objects.filter(column__subproject=subproject).select_related('assigned_to', 'column').prefetch_related('dependencies__column').order_by('created_at')
    all_project_tasks = Task.objects.filter(column__subproject__project=project).select_related('subproject', 'column').order_by('subproject__name', 'created_at')
    total_tasks_count = all_sub_tasks.count()
    personal_tasks_count = all_sub_tasks.filter(assigned_to=request.user).count()
    resources_count = subproject_resources.count()
    credentials_count = credentials.count()

    # Préparation des données JSON optimisées pour le moteur JavaScript du Gantt
    today = timezone.localdate()
    tasks_gantt_data = []
    for t in all_sub_tasks:
        start_d = t.start_date or (t.due_date if t.due_date else today)
        due_d = t.due_date or start_d
        
        assigned_name = t.assigned_to.first_name if (t.assigned_to and t.assigned_to.first_name) else (t.assigned_to.username if t.assigned_to else "Non assigné")
        assigned_avatar = (t.assigned_to.first_name[0] if t.assigned_to and t.assigned_to.first_name else (t.assigned_to.username[0] if t.assigned_to else "?")).upper()

        dep_ids = list(t.dependencies.values_list('id', flat=True))

        tasks_gantt_data.append({
            'id': t.id,
            'title': t.title,
            'description': t.description or '',
            'column_id': t.column_id,
            'column_name': t.column.name,
            'priority': t.priority,
            'priority_display': t.get_priority_display(),
            'start_date': t.start_date.strftime('%Y-%m-%d') if t.start_date else '',
            'due_date': t.due_date.strftime('%Y-%m-%d') if t.due_date else '',
            'has_due_date': bool(t.due_date),
            'assigned_id': str(t.assigned_to_id) if t.assigned_to_id else '',
            'assigned_name': (t.assigned_to.full_name if t.assigned_to else "Non assigné"),
            'assigned_email': (t.assigned_to.email if t.assigned_to else ""),
            'assigned_avatar': assigned_avatar,
            'is_blocked': t.has_unmet_dependencies(),
            'dependencies': dep_ids,
        })

    return render(request, 'projects/subproject_detail.html', {
        'project': project,
        'subproject': subproject,
        'sibling_subprojects': sibling_subprojects,
        'columns': columns,
        'credentials': credentials,
        'subproject_resources': subproject_resources,
        'parent_resources': parent_resources,
        'task_form': task_form,
        'assignable_users': assignable_users,
        'all_subproject_tasks': all_sub_tasks,
        'all_project_tasks': all_project_tasks,
        'credential_form': credential_form,
        'resource_form': resource_form,
        'edit_subproject_form': edit_subproject_form,
        'is_admin': is_admin,
        'total_tasks_count': total_tasks_count,
        'personal_tasks_count': personal_tasks_count,
        'resources_count': resources_count,
        'credentials_count': credentials_count,
        'today': today,
        'tasks_gantt_json': json.dumps(tasks_gantt_data),
        'active_tab': request.GET.get('tab', 'general'),
    })


@login_required
@require_POST
def subproject_edit_view(request, project_slug, subproject_slug):
    """
    Modification d'un sous-projet (nom et description).
    Strictement réservé au Chef de Projet ou à l'Administrateur.
    """
    project = get_object_or_404(Project, slug=project_slug)
    if not is_project_manager_or_admin(request.user, project):
        raise PermissionDenied("Seul le chef de projet ou l'administrateur a l'autorisation de modifier ce sous-projet.")

    subproject = get_object_or_404(SubProject, project=project, slug=subproject_slug)
    form = SubProjectForm(request.POST, instance=subproject)
    if form.is_valid():
        form.save()
        messages.success(request, f"Sous-projet « {subproject.name} » mis à jour avec succès.")
    else:
        messages.error(request, "Erreur lors de la modification du sous-projet.")

    return redirect('projects:subproject_detail', project_slug=project.slug, subproject_slug=subproject.slug)


@login_required
@require_POST
def subproject_delete_view(request, project_slug, subproject_slug):
    """
    Suppression d'un sous-projet.
    Strictement réservé au Chef de Projet ou à l'Administrateur.
    """
    project = get_object_or_404(Project, slug=project_slug)
    if not is_project_manager_or_admin(request.user, project):
        raise PermissionDenied("Seul le chef de projet ou l'administrateur a l'autorisation de supprimer ce sous-projet.")

    subproject = get_object_or_404(SubProject, project=project, slug=subproject_slug)
    subproject_name = subproject.name

    # Supprimer les fichiers physiques associés au sous-projet
    for res in subproject.resources.all():
        if res.file:
            try:
                res.file.delete(save=False)
            except Exception:
                pass

    subproject.delete()
    messages.success(request, f"Le sous-projet « {subproject_name} » a été supprimé.")
    return redirect('projects:project_detail', slug=project.slug)


@login_required
@require_POST
def task_create_view(request, project_slug, subproject_slug):
    """Création d'une tâche dans le sous-projet avec gestion des dépendances."""
    project = get_object_or_404(Project, slug=project_slug)
    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    subproject = get_object_or_404(SubProject, project=project, slug=subproject_slug)
    ensure_subproject_columns(subproject)

    form = TaskForm(request.POST, subproject=subproject)
    if form.is_valid():
        task = form.save(commit=False)
        task.subproject = subproject
        task.created_by = request.user

        # Colonne temporaire valide pour la sauvegarde initiale
        todo_col = subproject.columns.filter(name__iexact="À faire").first()
        task.column = todo_col
        task.save()
        form.save_m2m()  # Enregistre les dépendances sélectionnées

        # Vérification des dépendances pour le placement dans "En attente" ou "À faire"
        if task.has_unmet_dependencies():
            waiting_col = subproject.columns.filter(name__iexact="En attente").first()
            task.column = waiting_col
            task.save(update_fields=['column'])
            messages.info(request, f"Tâche « {task.title} » ajoutée. Elle est placée « En attente » car elle requiert des tâches préalables non terminées.")
        else:
            messages.success(request, f"Tâche « {task.title} » ajoutée avec succès.")
    else:
        messages.error(request, "Erreur lors de la création de la tâche.")

    redirect_tab = request.POST.get('redirect_tab', 'general')
    return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab={redirect_tab}")


@login_required
@require_POST
def task_edit_view(request, task_id):
    """Modification d'une tâche existante et recalcule de ses dépendances."""
    task = get_object_or_404(Task, id=task_id)
    subproject = task.column.subproject
    project = subproject.project

    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    is_manager_or_admin = is_project_manager_or_admin(request.user, project)
    is_assigned = (task.assigned_to_id == request.user.id)

    # Si la tâche dépend de prérequis non terminés, seul le chef de projet ou l'administrateur peut la modifier
    if task.has_unmet_dependencies() and not is_manager_or_admin:
        raise PermissionDenied("Seul le chef de projet ou l'administrateur est autorisé à modifier une tâche ayant des dépendances non terminées.")

    # Seuls l'administrateur, le chef de projet et l'utilisateur assigné peuvent modifier
    if not (is_manager_or_admin or is_assigned):
        raise PermissionDenied("Vous n'avez pas l'autorisation de modifier cette tâche.")

    if is_manager_or_admin:
        # Administrateur et Chef de projet : modification complète autorisée
        form = TaskForm(request.POST, instance=task, subproject=subproject)
        if form.is_valid():
            task = form.save()

            # Mise à jour de la colonne si les dépendances changent
            if task.has_unmet_dependencies():
                if task.column.name.strip().lower() != "en attente":
                    waiting_col = subproject.columns.filter(name__iexact="En attente").first()
                    if waiting_col:
                        task.column = waiting_col
                        task.save(update_fields=['column'])
            else:
                if task.column.name.strip().lower() == "en attente":
                    todo_col = subproject.columns.filter(name__iexact="À faire").first()
                    if todo_col:
                        task.column = todo_col
                        task.save(update_fields=['column'])

            messages.success(request, f"Tâche « {task.title} » modifiée avec succès.")
        else:
            messages.error(request, "Erreur lors de la modification de la tâche.")
    else:
        # Membre assigné : modification autorisée pour la description et les dates
        task.description = request.POST.get('description', '').strip()

        start_date_val = request.POST.get('start_date', '').strip()
        due_date_val = request.POST.get('due_date', '').strip()

        task.start_date = start_date_val if start_date_val else None
        task.due_date = due_date_val if due_date_val else None

        task.save(update_fields=['description', 'start_date', 'due_date'])
        messages.success(request, f"Tâche « {task.title} » mise à jour avec succès.")

    redirect_tab = request.POST.get('redirect_tab', 'general')
    return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab={redirect_tab}")


@login_required
@require_POST
def task_move_view(request, task_id):
    """Déplacement d'une tâche d'une colonne Kanban à une autre avec déblocage automatique en cascade."""
    task = get_object_or_404(Task, id=task_id)
    project = task.column.subproject.project

    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    is_manager_or_admin = is_project_manager_or_admin(request.user, project)
    is_assigned = (task.assigned_to_id == request.user.id)

    # Seuls l'administrateur, le chef de projet et l'utilisateur assigné peuvent déplacer l'état de la tâche
    if not (is_manager_or_admin or is_assigned):
        raise PermissionDenied("Seul le chef de projet, l'administrateur ou la personne assignée peut déplacer cette tâche.")

    column_id = request.POST.get('column_id')
    new_column = get_object_or_404(KanbanColumn, id=column_id, subproject=task.column.subproject)

    # 1. Interdiction stricte de déplacer manuellement une tâche vers "En attente"
    if new_column.name.strip().lower() == "en attente":
        messages.error(request, "La colonne « En attente » est gérée automatiquement par le système de dépendances.")
        return redirect('projects:subproject_detail', project_slug=project.slug, subproject_slug=task.column.subproject.slug)

    # 2. Bloquer le déplacement si la tâche a des dépendances non terminées
    if task.has_unmet_dependencies():
        messages.error(request, f"La tâche « {task.title} » est bloquée tant que ses tâches préalables ne sont pas terminées.")
        return redirect('projects:subproject_detail', project_slug=project.slug, subproject_slug=task.column.subproject.slug)

    old_col_name = task.column.name.strip().lower()
    new_col_name = new_column.name.strip().lower()

    task.column = new_column
    task.save(update_fields=['column'])

    # Si la tâche est passée dans "Terminé" :
    # Débloquer automatiquement les tâches dépendantes dont TOUTES les dépendances sont maintenant terminées
    if new_col_name == "terminé":
        for dep_task in task.dependent_tasks.all():
            if not dep_task.has_unmet_dependencies() and dep_task.column.name.strip().lower() == "en attente":
                todo_col = dep_task.subproject.columns.filter(name__iexact="À faire").first()
                if todo_col:
                    dep_task.column = todo_col
                    dep_task.save(update_fields=['column'])
                    messages.info(request, f"La tâche « {dep_task.title} » a été débloquée et déplacée dans « À faire » !")

    # Si la tâche était "Terminé" et qu'on la sort de "Terminé" :
    # Remettre "En attente" les tâches qui dépendent d'elle
    elif old_col_name == "terminé":
        for dep_task in task.dependent_tasks.all():
            if dep_task.has_unmet_dependencies() and dep_task.column.name.strip().lower() != "en attente":
                waiting_col = dep_task.subproject.columns.filter(name__iexact="En attente").first()
                if waiting_col:
                    dep_task.column = waiting_col
                    dep_task.save(update_fields=['column'])
                    messages.warning(request, f"La tâche « {dep_task.title} » a été replacée « En attente » car une de ses tâches préalables n'est plus terminée.")

    return redirect('projects:subproject_detail', project_slug=project.slug, subproject_slug=task.column.subproject.slug)


@login_required
@require_POST
def task_delete_view(request, task_id):
    """Suppression d'une tâche (réservé exclusivement au chef de projet et administrateur)."""
    task = get_object_or_404(Task, id=task_id)
    subproject = task.column.subproject
    project = subproject.project

    if not is_project_manager_or_admin(request.user, project):
        raise PermissionDenied("Seul le chef de projet ou l'administrateur peut supprimer une tâche.")

    # Avant suppression, vérifier si des tâches dépendaient d'elle
    dep_tasks = list(task.dependent_tasks.all())
    task.delete()

    # Débloquer les tâches dépendantes si elles n'ont plus d'autres dépendances non terminées
    for dep_task in dep_tasks:
        if not dep_task.has_unmet_dependencies() and dep_task.column.name.strip().lower() == "en attente":
            todo_col = dep_task.subproject.columns.filter(name__iexact="À faire").first()
            if todo_col:
                dep_task.column = todo_col
                dep_task.save(update_fields=['column'])

    messages.success(request, "Tâche supprimée.")
    return redirect('projects:subproject_detail', project_slug=project.slug, subproject_slug=subproject.slug)


@login_required
@require_POST
def credential_create_view(request, project_slug, subproject_slug):
    """Ajout d'un identifiant / mot de passe dans le sous-projet."""
    project = get_object_or_404(Project, slug=project_slug)
    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    subproject = get_object_or_404(SubProject, project=project, slug=subproject_slug)

    form = ProjectCredentialForm(request.POST)
    if form.is_valid():
        cred = form.save(commit=False)
        cred.subproject = subproject
        cred.save()
        messages.success(request, f"Accès « {cred.title} » enregistré dans le coffre-fort.")
    else:
        messages.error(request, "Erreur lors de l'enregistrement de l'accès.")

    return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab=passwords")


@login_required
@require_POST
def credential_delete_view(request, credential_id):
    """Suppression d'un mot de passe / accès."""
    cred = get_object_or_404(ProjectCredential, id=credential_id)
    subproject = cred.subproject
    project = subproject.project

    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    cred.delete()
    messages.success(request, "Accès supprimé du coffre-fort.")
    return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab=passwords")


@login_required
def credential_reveal_view(request, credential_id):
    """Déchiffrement et révélation sécurisée d'un mot de passe (chef de projet ou admin uniquement)."""
    cred = get_object_or_404(ProjectCredential, id=credential_id)
    project = cred.subproject.project

    if not is_project_manager_or_admin(request.user, project):
        raise PermissionDenied("Seul le chef de projet ou l'administrateur peut révéler ce secret.")

    credential_logger.info(
        "Révélation du secret credential_id=%s par user_id=%s (%s) projet=%s",
        cred.id, request.user.id, request.user.email, project.slug,
    )
    return JsonResponse({
        'password': cred.password_plaintext
    })


@login_required
@require_POST
def resource_create_view(request, project_slug, subproject_slug=None):
    """Ajout d'un document ou fichier (niveau projet global ou niveau sous-projet)."""
    project = get_object_or_404(Project, slug=project_slug)
    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    subproject = None
    if subproject_slug:
        subproject = get_object_or_404(SubProject, project=project, slug=subproject_slug)

    form = ProjectResourceForm(request.POST, request.FILES)
    if form.is_valid():
        res = form.save(commit=False)
        res.project = project
        res.subproject = subproject
        res.uploaded_by = request.user
        
        # Si aucun titre fourni et qu'un fichier est présent, on utilise le nom du fichier
        if not res.title:
            if res.file:
                res.title = res.file.name
            elif res.url:
                res.title = res.url
            else:
                res.title = "Document sans titre"

        res.save()
        messages.success(request, f"Document « {res.title} » ajouté avec succès.")
    else:
        messages.error(request, "Erreur lors de l'enregistrement du document / fichier.")

    if subproject:
        return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab=resources")
    return redirect('projects:project_detail', slug=project.slug)


@login_required
@require_POST
def resource_delete_view(request, resource_id):
    """
    Suppression d'un fichier ou document.
    Strictement réservé au Chef de Projet ou à l'Administrateur.
    """
    resource = get_object_or_404(ProjectResource, id=resource_id)
    project = resource.project
    if not is_project_manager_or_admin(request.user, project):
        raise PermissionDenied("Seul le chef de projet ou l'administrateur a l'autorisation de supprimer ce fichier ou document.")

    subproject = resource.subproject
    # Si c'est un fichier physique, suppression propre du disque
    if resource.file:
        try:
            resource.file.delete(save=False)
        except Exception:
            pass

    resource.delete()
    messages.success(request, "Document / Fichier supprimé.")

    if subproject:
        return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab=resources")
    return redirect('projects:project_detail', slug=project.slug)
