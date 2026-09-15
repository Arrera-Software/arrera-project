from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from .models import Project, SubProject, KanbanColumn, Task, ProjectCredential, ProjectResource
from .forms import ProjectForm, SubProjectForm, TaskForm, ProjectCredentialForm, ProjectResourceForm


def superuser_required(view_func):
    """Décorateur strict : bloque immédiatement les non-administrateurs avec une erreur 403."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_superuser:
            raise PermissionDenied("Seuls les administrateurs ont l'autorisation d'effectuer cette action.")
        return view_func(request, *args, **kwargs)
    return wrapper


def check_project_access(user, project):
    """Vérifie si l'utilisateur a le droit d'accéder au projet (admin, chef de projet ou membre assigné)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if project.manager_id and project.manager_id == user.id:
        return True
    return project.members.filter(id=user.id).exists()


def is_project_manager_or_admin(user, project):
    """Vérifie si l'utilisateur est administrateur ou chef de ce projet (tous les droits sur le projet)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return bool(project.manager_id and project.manager_id == user.id)


@login_required
@superuser_required
def project_create_view(request):
    """Création d'un nouveau projet principal (réservé à l'administrateur)."""
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            form.save_m2m()

            # Création automatique d'un premier sous-projet principal
            default_sub = SubProject.objects.create(
                project=project,
                name="Général",
                description="Sous-projet principal par défaut"
            )
            KanbanColumn.objects.create(subproject=default_sub, name="À faire", order=1)
            KanbanColumn.objects.create(subproject=default_sub, name="En cours", order=2)
            KanbanColumn.objects.create(subproject=default_sub, name="Terminé", order=3)

            messages.success(request, f"Le projet « {project.name} » a été créé.")
            return redirect('projects:project_detail', slug=project.slug)
    else:
        form = ProjectForm()

    return render(request, 'projects/project_form.html', {
        'form': form,
        'action_title': "Nouveau Projet",
        'button_label': "Créer le Projet",
    })


@login_required
def project_edit_view(request, slug):
    """
    Modification d'un projet existant (nom, description, chef de projet, membres assignés).
    Accessible à l'administrateur et au chef de projet désigné.
    """
    project = get_object_or_404(Project, slug=slug)
    if not is_project_manager_or_admin(request.user, project):
        raise PermissionDenied("Vous n'avez pas les droits d'administration sur ce projet.")

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save()
            messages.success(request, f"Les paramètres du projet « {project.name} » ont été enregistrés.")
            return redirect('projects:project_detail', slug=project.slug)
    else:
        form = ProjectForm(instance=project)

    return render(request, 'projects/project_form.html', {
        'form': form,
        'action_title': f"Paramètres de {project.name}",
        'button_label': "Enregistrer les modifications",
        'is_edit': True,
        'project': project,
    })


@login_required
def project_detail_view(request, slug):
    """
    Page du Projet Principal :
    Affiche les détails du projet, le chef de projet, l'équipe affectée, la liste des sous-projets
    et la section des documents & fichiers.
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

    return render(request, 'projects/project_detail.html', {
        'project': project,
        'subprojects': subprojects,
        'subproject_form': subproject_form,
        'resource_form': resource_form,
        'project_resources': project_resources,
        'all_resources': all_resources,
        'is_admin': is_admin,
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

        # Création des colonnes Kanban par défaut
        KanbanColumn.objects.create(subproject=subproject, name="À faire", order=1)
        KanbanColumn.objects.create(subproject=subproject, name="En cours", order=2)
        KanbanColumn.objects.create(subproject=subproject, name="Terminé", order=3)

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
    columns = subproject.columns.prefetch_related('tasks__assigned_to').all()
    credentials = subproject.credentials.all()
    
    # Documents / Fichiers du sous-projet + documents globaux du projet parent
    subproject_resources = subproject.resources.all()
    parent_resources = project.resources.filter(subproject__isnull=True)
    resources_count = subproject_resources.count() + parent_resources.count()

    task_form = TaskForm(subproject=subproject)
    credential_form = ProjectCredentialForm()
    resource_form = ProjectResourceForm()

    active_tab = request.GET.get('tab', 'general')
    
    all_tasks = subproject.tasks.select_related('column', 'assigned_to').all()
    total_tasks_count = all_tasks.count()
    personal_tasks_count = all_tasks.filter(assigned_to=request.user).count()
    credentials_count = credentials.count()

    # Données pour le calendrier Gantt
    tasks_gantt_list = []
    for t in all_tasks:
        s_date = t.start_date or t.created_at.date()
        d_date = t.due_date or s_date
        tasks_gantt_list.append({
            'id': t.id,
            'title': t.title,
            'description': t.description or '',
            'column_name': t.column.name,
            'column_id': t.column.id,
            'priority': t.priority,
            'priority_label': t.get_priority_display(),
            'start_date': s_date.isoformat(),
            'due_date': t.due_date.isoformat() if t.due_date else '',
            'has_due_date': bool(t.due_date),
            'effective_end_date': d_date.isoformat(),
            'assigned_name': t.assigned_to.full_name if t.assigned_to else (t.assigned_to.username if t.assigned_to else 'Non assigné'),
            'assigned_avatar': (t.assigned_to.first_name[:1] if t.assigned_to and t.assigned_to.first_name else (t.assigned_to.username[:1].upper() if t.assigned_to else '?')),
        })

    sibling_subprojects = project.subprojects.all()
    is_admin = is_project_manager_or_admin(request.user, project)

    return render(request, 'projects/subproject_detail.html', {
        'project': project,
        'subproject': subproject,
        'sibling_subprojects': sibling_subprojects,
        'columns': columns,
        'credentials': credentials,
        'subproject_resources': subproject_resources,
        'parent_resources': parent_resources,
        'resources_count': resources_count,
        'task_form': task_form,
        'credential_form': credential_form,
        'resource_form': resource_form,
        'active_tab': active_tab,
        'total_tasks_count': total_tasks_count,
        'personal_tasks_count': personal_tasks_count,
        'credentials_count': credentials_count,
        'tasks_gantt_json': json.dumps(tasks_gantt_list),
        'is_admin': is_admin,
    })


@login_required
@require_POST
def task_create_view(request, project_slug, subproject_slug):
    """Création d'une tâche dans le sous-projet."""
    project = get_object_or_404(Project, slug=project_slug)
    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    subproject = get_object_or_404(SubProject, project=project, slug=subproject_slug)
    form = TaskForm(request.POST, subproject=subproject)
    if form.is_valid():
        task = form.save(commit=False)
        task.subproject = subproject
        task.save()
        messages.success(request, f"Tâche « {task.title} » ajoutée.")
    else:
        messages.error(request, "Erreur lors de la création de la tâche.")

    redirect_tab = request.POST.get('redirect_tab', 'general')
    return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab={redirect_tab}")


@login_required
@require_POST
def task_move_view(request, task_id):
    """Déplacement d'une tâche vers une autre colonne."""
    task = get_object_or_404(Task, id=task_id)
    if not check_project_access(request.user, task.subproject.project):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    target_column_id = request.POST.get('column_id')
    column = get_object_or_404(KanbanColumn, id=target_column_id, subproject=task.subproject)
    task.column = column
    task.save()

    return JsonResponse({'success': True, 'task_id': task.id, 'column_id': column.id})


@login_required
@require_POST
def task_delete_view(request, task_id):
    """Suppression d'une tâche."""
    task = get_object_or_404(Task, id=task_id)
    subproject = task.subproject
    project = subproject.project
    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    task.delete()
    messages.success(request, "Tâche supprimée.")
    redirect_tab = request.POST.get('redirect_tab', 'general')
    return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab={redirect_tab}")


@login_required
@require_POST
def credential_create_view(request, project_slug, subproject_slug):
    """Ajout d'un identifiant / mot de passe dans le coffre-fort du sous-projet."""
    project = get_object_or_404(Project, slug=project_slug)
    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    subproject = get_object_or_404(SubProject, project=project, slug=subproject_slug)
    form = ProjectCredentialForm(request.POST)
    if form.is_valid():
        credential = form.save(commit=False)
        credential.subproject = subproject
        credential.save()
        messages.success(request, f"Identifiant « {credential.title} » enregistré.")
    else:
        messages.error(request, "Erreur lors de l'enregistrement de l'accès.")

    return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab=passwords")


@login_required
@require_POST
def credential_delete_view(request, credential_id):
    """Suppression d'un mot de passe du coffre-fort."""
    credential = get_object_or_404(ProjectCredential, id=credential_id)
    subproject = credential.subproject
    project = subproject.project
    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    credential.delete()
    messages.success(request, "Accès supprimé du coffre-fort.")
    return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab=passwords")


@login_required
@require_POST
def resource_create_view(request, project_slug, subproject_slug=None):
    """Ajout ou téléversement d'un document ou fichier (attaché à un projet ou à un sous-projet)."""
    project = get_object_or_404(Project, slug=project_slug)
    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    subproject = None
    if subproject_slug:
        subproject = get_object_or_404(SubProject, project=project, slug=subproject_slug)

    form = ProjectResourceForm(request.POST, request.FILES)
    if form.is_valid():
        resource = form.save(commit=False)
        resource.project = project
        resource.subproject = subproject
        resource.created_by = request.user
        resource.save()
        messages.success(request, f"Fichier / Document « {resource.title} » ajouté avec succès.")
    else:
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f"{err}")

    if subproject:
        return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab=resources")
    return redirect('projects:project_detail', slug=project.slug)


@login_required
@require_POST
def resource_delete_view(request, resource_id):
    """Suppression d'un fichier ou document."""
    resource = get_object_or_404(ProjectResource, id=resource_id)
    project = resource.project
    if not check_project_access(request.user, project):
        raise PermissionDenied("Accès refusé.")

    subproject = resource.subproject
    # Si c'est un fichier physique, on le supprime également du disque
    if resource.file:
        try:
            resource.file.delete(save=False)
        except Exception:
            pass

    resource.delete()
    messages.success(request, "Fichier / Document supprimé.")

    if subproject:
        return redirect(f"/projets/{project.slug}/{subproject.slug}/?tab=resources")
    return redirect('projects:project_detail', slug=project.slug)
