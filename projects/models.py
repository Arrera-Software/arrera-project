import os
import uuid
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.urls import reverse
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# Clé de dérivation Fernet pour le chiffrement des secrets du coffre-fort.
_SALT = b"arrera-vault-static-salt-2026"
_kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=_SALT,
    iterations=100_000,
)
_ENCRYPTION_KEY = base64.urlsafe_b64encode(_kdf.derive(settings.SECRET_KEY.encode()))
_cipher = Fernet(_ENCRYPTION_KEY)


class Project(models.Model):
    """
    Modèle Projet principal.
    Géré par l'Administrateur, supervisé par un Chef de projet, et partagé avec des Membres.
    """
    class Visibility(models.TextChoices):
        INTERNAL = 'internal', 'Interne (Membres assignés)'
        PUBLIC = 'public', 'Public (Tous les utilisateurs)'

    name = models.CharField("Nom du projet", max_length=200)
    slug = models.SlugField("Identifiant unique (slug)", max_length=220, unique=True, blank=True)
    description = models.TextField("Description", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_projects',
        verbose_name="Créé par (Admin)"
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_projects',
        verbose_name="Chef de projet"
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='joined_projects',
        verbose_name="Membres de l'équipe"
    )
    created_at = models.DateTimeField("Date de création", auto_now_add=True)
    updated_at = models.DateTimeField("Dernière mise à jour", auto_now=True)

    class Meta:
        verbose_name = "Projet"
        verbose_name_plural = "Projets"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "projet"
            unique_slug = base_slug
            counter = 1
            while Project.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'slug': self.slug})


class SubProject(models.Model):
    """
    Modèle Sous-Projet rattaché à un projet principal.
    Chaque sous-projet dispose de son propre tableau Kanban, timeline Gantt et coffre-fort de mots de passe.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='subprojects', verbose_name="Projet parent")
    name = models.CharField("Nom du sous-projet", max_length=200)
    slug = models.SlugField("Identifiant unique (slug)", max_length=220, blank=True)
    description = models.TextField("Description", blank=True)
    created_at = models.DateTimeField("Date de création", auto_now_add=True)
    updated_at = models.DateTimeField("Dernière mise à jour", auto_now=True)

    class Meta:
        verbose_name = "Sous-projet"
        verbose_name_plural = "Sous-projets"
        unique_together = ('project', 'slug')
        ordering = ['created_at']

    def __str__(self):
        return f"{self.project.name} → {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "sous-projet"
            unique_slug = base_slug
            counter = 1
            while SubProject.objects.filter(project=self.project, slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)


class KanbanColumn(models.Model):
    """Colonnes du tableau Kanban pour chaque sous-projet."""
    subproject = models.ForeignKey(SubProject, on_delete=models.CASCADE, related_name='columns')
    name = models.CharField("Nom de la colonne", max_length=100)
    order = models.PositiveIntegerField("Ordre d'affichage", default=0)

    class Meta:
        verbose_name = "Colonne Kanban"
        verbose_name_plural = "Colonnes Kanban"
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.subproject.name} - {self.name}"


class Task(models.Model):
    """Tâche d'un sous-projet assignable aux membres de l'équipe."""
    class Priority(models.TextChoices):
        LOW = 'low', 'Basse'
        MEDIUM = 'medium', 'Moyenne'
        HIGH = 'high', 'Haute'
        URGENT = 'urgent', 'Urgente'

    subproject = models.ForeignKey(SubProject, on_delete=models.CASCADE, related_name='tasks')
    column = models.ForeignKey(KanbanColumn, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField("Titre de la tâche", max_length=255)
    description = models.TextField("Description détaillée", blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
        verbose_name="Assigné à"
    )
    priority = models.CharField(
        "Priorité",
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    dependencies = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='dependent_tasks',
        blank=True,
        verbose_name="Tâches préalables requises"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tasks',
        verbose_name="Créé par"
    )
    start_date = models.DateField("Date de début", null=True, blank=True)
    due_date = models.DateField("Date limite", null=True, blank=True)
    created_at = models.DateTimeField("Créé le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifié le", auto_now=True)

    class Meta:
        verbose_name = "Tâche"
        verbose_name_plural = "Tâches"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def effective_start_date(self):
        return self.start_date or self.created_at.date()

    def has_unmet_dependencies(self):
        """Vérifie si la tâche a des dépendances qui ne sont pas encore dans l'état Terminé."""
        return self.dependencies.exclude(column__name__iexact="Terminé").exists()

    def get_unmet_dependencies(self):
        """Renvoie la liste des tâches préalables non terminées."""
        return self.dependencies.exclude(column__name__iexact="Terminé")


class ProjectCredential(models.Model):
    """
    Gestionnaire de mots de passe et accès intégré au sous-projet.
    Le mot de passe est stocké CHIFFRÉ (Fernet) dans le champ `password`.
    On y accède en clair via la propriété `password_plaintext` / `set_secret()`.
    """
    subproject = models.ForeignKey(SubProject, on_delete=models.CASCADE, related_name='credentials')
    title = models.CharField("Intitulé de l'accès", max_length=150)
    service_url = models.CharField("URL / Serveur / Hôte", max_length=255, blank=True)
    username = models.CharField("Identifiant / Login", max_length=150, blank=True)
    # Contient le secret CHIFFRÉ (préfixe `enc:`). Longueur augmentée pour le ciphertext.
    password = models.CharField("Mot de passe / Clé secrète (chiffré)", max_length=512)
    notes = models.TextField("Notes / Consignes d'accès", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Accès & Mot de passe"
        verbose_name_plural = "Accès & Mots de passe"
        ordering = ['title']

    def __str__(self):
        return f"{self.subproject.name} - {self.title}"

    def set_secret(self, raw_password: str):
        """Chiffre le mot de passe avant stockage."""
        if not raw_password:
            self.password = ""
            return
        encrypted = _cipher.encrypt(raw_password.encode('utf-8')).decode('utf-8')
        self.password = f"enc:{encrypted}"

    @property
    def password_plaintext(self) -> str:
        """Déchiffre le mot de passe stocké."""
        if not self.password:
            return ""
        if self.password.startswith("enc:"):
            token = self.password[4:].encode('utf-8')
            try:
                return _cipher.decrypt(token).decode('utf-8')
            except Exception:
                return "« Erreur de déchiffrement »"
        # Rétrocompatibilité données non-chiffrées
        return self.password


class ProjectResource(models.Model):
    """
    Documents, fichiers joints et liens attachés à un projet ou à un sous-projet.
    Si `subproject` est NULL, le fichier appartient au projet global.
    """
    class ResourceType(models.TextChoices):
        DOCUMENT = 'document', 'Document'
        FILE = 'file', 'Fichier'
        LINK = 'link', 'Lien externe'
        DESIGN = 'design', 'Maquette (Figma, etc.)'
        REPO = 'repo', 'Dépôt Git / Code'
        OTHER = 'other', 'Autre'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='resources', verbose_name="Projet")
    subproject = models.ForeignKey(SubProject, on_delete=models.CASCADE, null=True, blank=True, related_name='resources', verbose_name="Sous-projet")
    title = models.CharField("Titre du document", max_length=200)
    resource_type = models.CharField("Type", max_length=20, choices=ResourceType.choices, default=ResourceType.DOCUMENT)
    file = models.FileField("Fichier uploadé", upload_to='project_resources/%Y/%m/', blank=True, null=True)
    url = models.URLField("Lien externe", blank=True)
    description = models.TextField("Notes / Description", blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_resources',
        verbose_name="Ajouté par"
    )
    created_at = models.DateTimeField("Ajouté le", auto_now_add=True)

    class Meta:
        verbose_name = "Document / Ressource"
        verbose_name_plural = "Documents & Ressources"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_file(self):
        return bool(self.file)

    @property
    def file_extension(self):
        if self.file:
            return os.path.splitext(self.file.name)[1].lstrip('.').upper()
        return ""

    @property
    def file_size_formatted(self):
        if self.file and hasattr(self.file, 'size'):
            size = self.file.size
            for unit in ['o', 'Ko', 'Mo', 'Go']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
        return ""
