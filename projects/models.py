import os
from django.db import models
from django.conf import settings
from django.utils.text import slugify


class Project(models.Model):
    """
    Modèle Projet Principal Arrera.
    Seul l'administrateur (superutilisateur) peut en créer.
    Un chef de projet peut être désigné et aura tous les droits sur ce projet.
    """
    name = models.CharField("Nom du projet", max_length=200)
    slug = models.SlugField("Identifiant unique (slug)", max_length=220, unique=True, blank=True)
    description = models.TextField("Description", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_projects',
        verbose_name="Créateur (Admin)"
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
        related_name='assigned_projects',
        blank=True,
        verbose_name="Membres assignés"
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


class ProjectCredential(models.Model):
    """Gestionnaire de mots de passe et accès intégré au sous-projet."""
    subproject = models.ForeignKey(SubProject, on_delete=models.CASCADE, related_name='credentials')
    title = models.CharField("Intitulé de l'accès", max_length=150)
    service_url = models.CharField("URL / Serveur / Hôte", max_length=255, blank=True)
    username = models.CharField("Identifiant / Login", max_length=150, blank=True)
    password = models.CharField("Mot de passe / Clé secrète", max_length=255)
    notes = models.TextField("Notes / Consignes d'accès", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Accès & Mot de passe"
        verbose_name_plural = "Accès & Mots de passe"
        ordering = ['title']

    def __str__(self):
        return f"{self.subproject.name} - {self.title}"


class ProjectResource(models.Model):
    """
    Modèle Ressource / Document / Fichier physique ou Lien externe.
    Permet de téléverser directement des fichiers physiques (PDF, archives ZIP, tableurs, etc.)
    ou de centraliser des liens externes (Notion, Google Docs, Figma, dépôts Git).
    Peut être associé au projet principal ou à un sous-projet spécifique.
    """
    class EntryType(models.TextChoices):
        FILE = 'file', 'Fichier téléversé'
        URL = 'url', 'Lien web / URL externe'

    class ResourceType(models.TextChoices):
        DOCUMENT = 'document', 'Documentation / PDF'
        FILE = 'file', 'Fichier / Archive'
        DESIGN = 'design', 'Design / Maquettes'
        REPO = 'repo', 'Dépôt / Code source'
        OTHER = 'other', 'Autre document'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='resources', verbose_name="Projet")
    subproject = models.ForeignKey(SubProject, on_delete=models.CASCADE, null=True, blank=True, related_name='resources', verbose_name="Sous-projet (optionnel)")
    entry_type = models.CharField("Type d'entrée", max_length=10, choices=EntryType.choices, default=EntryType.FILE)
    title = models.CharField("Nom du document / fichier", max_length=200, blank=True)
    file = models.FileField("Fichier téléversé", upload_to='project_files/%Y/%m/', null=True, blank=True)
    url = models.URLField("Lien URL externe", max_length=500, blank=True)
    resource_type = models.CharField("Catégorie", max_length=20, choices=ResourceType.choices, default=ResourceType.DOCUMENT)
    file_size = models.PositiveBigIntegerField("Taille en octets", default=0, blank=True)
    description = models.TextField("Description / Notes", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ajouté par")
    created_at = models.DateTimeField("Ajouté le", auto_now_add=True)
    updated_at = models.DateTimeField("Mis à jour le", auto_now=True)

    class Meta:
        verbose_name = "Document & Fichier"
        verbose_name_plural = "Documents & Fichiers"
        ordering = ['-created_at']

    def __str__(self):
        return self.title or self.file_name or "Document"

    def save(self, *args, **kwargs):
        if self.file and hasattr(self.file, 'size') and self.file.size:
            self.file_size = self.file.size
        if not self.title:
            if self.file:
                self.title = os.path.basename(self.file.name)
            elif self.url:
                self.title = self.url
            else:
                self.title = "Document"
        super().save(*args, **kwargs)

    @property
    def is_file(self):
        return bool(self.file)

    @property
    def target_url(self):
        if self.file:
            return self.file.url
        return self.url

    @property
    def file_name(self):
        if self.file:
            return os.path.basename(self.file.name)
        return ""

    @property
    def file_extension(self):
        if self.file:
            _, ext = os.path.splitext(self.file.name)
            return ext.replace('.', '').upper()
        return ""

    @property
    def file_size_formatted(self):
        if not self.file_size:
            return ""
        size = self.file_size
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if size < 1024.0:
                return f"{size:.1f} {unit}".replace('.0 ', ' ')
            size /= 1024.0
        return f"{size:.1f} To"
