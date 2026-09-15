from django import forms
from .models import Project, SubProject, Task, ProjectCredential, KanbanColumn
from django.contrib.auth import get_user_model

User = get_user_model()


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
    """Formulaire d'ajout ou modification d'une tâche."""
    class Meta:
        model = Task
        fields = ['title', 'description', 'column', 'assigned_to', 'priority', 'due_date']
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
    """Formulaire d'ajout d'un mot de passe / accès dans un sous-projet."""
    class Meta:
        model = ProjectCredential
        fields = ['title', 'service_url', 'username', 'password', 'notes']
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
            'password': forms.PasswordInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Mot de passe ou clé secrète',
                'render_value': True,
                'required': True,
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 rounded-2xl text-sm adw-input',
                'placeholder': 'Notes supplémentaires, ports, certificats...',
                'rows': 3,
            }),
        }
