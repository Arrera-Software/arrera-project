from django.db import models
from django.conf import settings
from django.utils.text import slugify
import uuid


class Project(models.Model):
    """
    Modèle Projet Arrera.
    Seul l'administrateur (superutilisateur) peut en créer.
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


class KanbanColumn(models.Model):
    """Colonnes du tableau Kanban pour chaque projet."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='columns')
    name = models.CharField("Nom de la colonne", max_length=100)
    order = models.PositiveIntegerField("Ordre d'affichage", default=0)

    class Meta:
        verbose_name = "Colonne Kanban"
        verbose_name_plural = "Colonnes Kanban"
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class Task(models.Model):
    """Tâche d'un projet assignable aux membres."""
    class Priority(models.TextChoices):
        LOW = 'low', 'Basse'
        MEDIUM = 'medium', 'Moyenne'
        HIGH = 'high', 'Haute'
        URGENT = 'urgent', 'Urgente'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
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
    due_date = models.DateField("Date limite", null=True, blank=True)
    created_at = models.DateTimeField("Créé le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifié le", auto_now=True)

    class Meta:
        verbose_name = "Tâche"
        verbose_name_plural = "Tâches"
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ProjectCredential(models.Model):
    """Gestionnaire de mots de passe et accès intégré au projet."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='credentials')
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
        return f"{self.project.name} - {self.title}"
