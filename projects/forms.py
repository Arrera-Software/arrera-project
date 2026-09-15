import os
from django import forms
from django.conf import settings
from .models import Project, SubProject, Task, ProjectCredential, ProjectResource, KanbanColumn
from django.contrib.auth import get_user_model

User = get_user_model()

# Extensions autorisées au téléversement (liste blanche).
# Les formats exécutables dans un navigateur (svg, html, js...) sont exclus
# pour empêcher le XSS stocké via fichier servi sur le même domaine.
ALLOWED_UPLOAD_EXTENSIONS = {
    'pdf', 'txt', 'csv', 'md', 'rtf',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'odp',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp',
    'zip', 'tar', 'gz', '7z', 'rar',
}


class UserModelChoiceField(forms.ModelChoiceField):
    """Champ de sélection d'un utilisateur unique avec nom complet et email."""
    def label_from_instance(self, obj):
        return f"{obj.full_name} ({obj.email})" if obj.full_name != obj.username else f"{obj.username} ({obj.email})"


class UserModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Champ de sélection de membres avec affichage du nom complet et de l'email."""
    def label_from_instance(self, obj):
        return f"{obj.full_name} ({obj.email})" if obj.full_name != obj.username else f"{obj.username} ({obj.email})"


class ProjectForm(forms.ModelForm):
    """
    Formulaire de création et édition d'un projet principal.
    Permet de définir le chef de projet et l'équipe affectée.
    """
    manager = UserModelChoiceField(
        queryset=User.objects.filter(is_active=True, is_superuser=False),
        required=False,
        empty_label="-- Aucun (ou définir plus tard) --",
        label="Chef de projet",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-2xl text-sm adw-input cursor-pointer',
        })
    )

    members = UserModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True, is_superuser=False),
        required=False,
        label="Membres assignés",
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Project
        fields = ['name', 'description', 'manager', 'members']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl text-sm adw-input',
                'placeholder': 'ex: Arrera Assistant OS',
                'autofocus': True,
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl text-sm adw-input',
                'placeholder': 'Description globale et objectifs du projet...',
                'rows': 4,
            }),
        }


class SubProjectForm(forms.ModelForm):
    """Formulaire de création et édition d'un sous-projet."""
    class Meta:
        model = SubProject
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'ex: Interface Graphique, Backend API, Module Sécurité...',
                'autofocus': True,
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Description du sous-projet...',
                'rows': 3,
            }),
        }


class TaskForm(forms.ModelForm):
    """Formulaire d'ajout ou modification d'une tâche avec dates de début et deadline."""
    class Meta:
        model = Task
        fields = ['title', 'description', 'column', 'assigned_to', 'priority', 'start_date', 'due_date']
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
            'column': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input cursor-pointer',
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input cursor-pointer',
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
        }

    def __init__(self, *args, subproject=None, **kwargs):
        super().__init__(*args, **kwargs)
        if subproject:
            self.fields['column'].queryset = subproject.columns.all()
            project = subproject.project
            manager_qs = User.objects.filter(id=project.manager_id) if project.manager_id else User.objects.none()
            self.fields['assigned_to'].queryset = (project.members.all() | User.objects.filter(is_superuser=True) | manager_qs).distinct()
            self.fields['assigned_to'].label_from_instance = lambda obj: f"{obj.full_name} ({obj.email})"
            self.fields['assigned_to'].empty_label = "-- Non assigné --"


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
        })
    )

    class Meta:
        model = ProjectCredential
        fields = ['title', 'service_url', 'username', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'ex: Serveur SSH Production, Base PostgreSQL...',
                'required': True,
            }),
            'service_url': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'https://admin.exemple.com ou vps.arrera.local',
            }),
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Identifiant / Login / Utilisateur',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Notes supplémentaires, ports, certificats...',
                'rows': 3,
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
    class Meta:
        model = ProjectResource
        fields = ['entry_type', 'title', 'file', 'url', 'resource_type', 'description']
        widgets = {
            'entry_type': forms.RadioSelect(attrs={
                'class': 'hidden',
            }),
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
        title = cleaned_data.get('title')

        if entry_type == 'file':
            if not uploaded_file and not self.instance.file:
                raise forms.ValidationError({'file': "Veuillez sélectionner un fichier à téléverser."})
            # Si le titre est vide, utiliser le nom du fichier par défaut
            if not title and uploaded_file:
                cleaned_data['title'] = os.path.basename(uploaded_file.name)
        elif entry_type == 'url':
            if not url:
                raise forms.ValidationError({'url': "Veuillez renseigner un lien URL valide."})
            if not title:
                cleaned_data['title'] = url

        return cleaned_data
