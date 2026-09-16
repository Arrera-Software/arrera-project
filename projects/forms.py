import os
from django import forms
from django.contrib.auth import get_user_model
from django.conf import settings
from .models import Project, SubProject, Task, ProjectCredential, ProjectResource

User = get_user_model()

ALLOWED_UPLOAD_EXTENSIONS = {
    'pdf', 'png', 'jpg', 'jpeg', 'webp', 'svg', 'gif',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'txt', 'md',
    'zip', 'rar', 'tar', 'gz', '7z',
}


class ProjectForm(forms.ModelForm):
    """
    Formulaire de création / édition d'un projet principal.
    Permet d'assigner un Chef de projet et une équipe de Membres (hors superutilisateurs).
    """
    class Meta:
        model = Project
        fields = ['name', 'description', 'manager', 'members']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'ex: Refonte Site Arrera 2026',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Objectifs du projet, périmètre, planning...',
                'rows': 3,
            }),
            'manager': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input cursor-pointer',
            }),
            'members': forms.CheckboxSelectMultiple(attrs={
                'class': 'space-y-2',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclure les superutilisateurs de la sélection de chef de projet et des membres
        active_non_superusers = User.objects.filter(is_active=True, is_superuser=False).order_by('first_name', 'username')
        self.fields['manager'].queryset = active_non_superusers
        self.fields['manager'].empty_label = "— Aucun chef de projet désigné —"
        self.fields['manager'].required = False
        self.fields['members'].queryset = active_non_superusers
        self.fields['members'].required = False


class SubProjectForm(forms.ModelForm):
    """Formulaire de création d'un sous-projet."""
    class Meta:
        model = SubProject
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'ex: Frontend, API Backend, Documentation...',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Description du périmètre du sous-projet...',
                'rows': 3,
            }),
        }


class TaskForm(forms.ModelForm):
    """Formulaire d'ajout ou modification d'une tâche avec dates de début, deadline et dépendances."""
    class Meta:
        model = Task
        fields = ['title', 'description', 'assigned_to', 'priority', 'start_date', 'due_date', 'dependencies']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Titre de la tâche...',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Détails, spécifications...',
                'rows': 3,
            }),
            'assigned_to': forms.HiddenInput(attrs={
                'id': 'task-assigned-to-input',
            }),
            'priority': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input cursor-pointer',
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
            }),
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
            }),
            'dependencies': forms.CheckboxSelectMultiple(attrs={
                'class': 'space-y-1.5',
            }),
        }

    def __init__(self, *args, subproject=None, **kwargs):
        super().__init__(*args, **kwargs)
        if subproject:
            project = subproject.project
            manager_qs = User.objects.filter(id=project.manager_id, is_active=True, is_superuser=False) if project.manager_id else User.objects.none()
            self.fields['assigned_to'].queryset = (project.members.filter(is_active=True, is_superuser=False) | manager_qs).distinct()
            self.fields['assigned_to'].required = False

            # Dépendances ouvertes à l'ensemble des tâches du projet (tous sous-projets confondus)
            tasks_qs = Task.objects.filter(column__subproject__project=project).select_related('subproject', 'column')
            if self.instance and self.instance.pk:
                tasks_qs = tasks_qs.exclude(pk=self.instance.pk)
            self.fields['dependencies'].queryset = tasks_qs
            self.fields['dependencies'].required = False

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        due_date = cleaned_data.get('due_date')
        dependencies = cleaned_data.get('dependencies')

        if start_date and due_date and due_date < start_date:
            self.add_error('due_date', "La date d'échéance ne peut pas être antérieure à la date de début.")

        if dependencies:
            latest_dep_date = None
            blocking_task_title = ""

            for dep in dependencies:
                dep_ref_date = dep.due_date or dep.start_date
                if dep_ref_date and (latest_dep_date is None or dep_ref_date > latest_dep_date):
                    latest_dep_date = dep_ref_date
                    blocking_task_title = dep.title

            if latest_dep_date:
                if start_date and start_date < latest_dep_date:
                    self.add_error(
                        'start_date',
                        f"La date de début ({start_date.strftime('%d/%m/%Y')}) ne peut pas être antérieure à la fin de la tâche requise « {blocking_task_title} » ({latest_dep_date.strftime('%d/%m/%Y')})."
                    )
                elif not start_date and due_date and due_date < latest_dep_date:
                    self.add_error(
                        'due_date',
                        f"La date d'échéance ({due_date.strftime('%d/%m/%Y')}) ne peut pas être antérieure à la fin de la tâche requise « {blocking_task_title} » ({latest_dep_date.strftime('%d/%m/%Y')})."
                    )

        return cleaned_data


class ProjectCredentialForm(forms.ModelForm):
    """
    Formulaire d'ajout d'un mot de passe / accès dans un sous-projet.
    Le secret saisi est chiffré avant enregistrement (jamais stocké en clair).
    """
    # Champ non-modèle : le mot de passe en clair saisi par l'utilisateur.
    password = forms.CharField(
        label="Mot de passe / Clé secrète",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
            'placeholder': 'Mot de passe ou clé secrète',
            'render_value': False,
            'required': True,
        }),
    )

    class Meta:
        model = ProjectCredential
        fields = ['title', 'service_url', 'username', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'ex: Compte Cloud AWS Prod, Accès SSH, BDD...',
                'required': True,
            }),
            'service_url': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'ex: https://aws.amazon.com ou ssh.mondomaine.fr',
            }),
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'ex: admin, deploy@serveur.com...',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Consignes de sécurité, rotation, ports...',
                'rows': 2,
            }),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Chiffre le secret saisi avant persistance.
        instance.set_secret(self.cleaned_data.get('password', ''))
        if commit:
            instance.save()
        return instance


class ProjectResourceForm(forms.ModelForm):
    """
    Formulaire d'ajout d'un fichier téléversé ou d'un lien web.
    Permet à l'utilisateur de charger directement des fichiers (PDF, ZIP, images...)
    ou d'ajouter un lien externe (Google Docs, Figma, GitHub...).
    """
    entry_type = forms.ChoiceField(
        choices=[('file', 'Fichier'), ('url', 'Lien web')],
        initial='file',
        widget=forms.RadioSelect(attrs={'class': 'hidden'}),
        required=False
    )

    class Meta:
        model = ProjectResource
        fields = ['title', 'file', 'url', 'resource_type', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'ex: Cahier des charges, Maquettes Figma, Spécifications v1...',
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 rounded-2xl text-sm adw-input cursor-pointer file:mr-4 file:py-1 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-[var(--accent)] file:text-white hover:file:opacity-90',
            }),
            'url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'https://docs.google.com/... ou https://figma.com/...',
            }),
            'resource_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input cursor-pointer',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Description, remarques ou consignes...',
                'rows': 2,
            }),
        }

    def clean_file(self):
        """Valide l'extension et la taille du fichier téléversé (liste blanche)."""
        uploaded_file = self.cleaned_data.get('file')
        if not uploaded_file or not getattr(uploaded_file, 'name', ''):
            return uploaded_file

        ext = os.path.splitext(uploaded_file.name)[1].lower().lstrip('.')
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise forms.ValidationError(
                "Type de fichier non autorisé. Extensions acceptées : "
                + ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS)) + "."
            )

        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 25 * 1024 * 1024)
        if getattr(uploaded_file, 'size', 0) > max_size:
            raise forms.ValidationError(
                f"Fichier trop volumineux (max {max_size // (1024 * 1024)} Mo)."
            )
        return uploaded_file

    def clean(self):
        cleaned_data = super().clean()
        entry_type = cleaned_data.get('entry_type') or 'file'
        uploaded_file = cleaned_data.get('file')
        url = cleaned_data.get('url')

        if entry_type == 'file' and not uploaded_file:
            raise forms.ValidationError("Veuillez sélectionner un fichier à téléverser.")
        if entry_type == 'url' and not url:
            raise forms.ValidationError("Veuillez saisir une URL valide.")

        return cleaned_data
