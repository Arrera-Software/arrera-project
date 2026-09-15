from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Modèle utilisateur personnalisé pour Arrera Project.
    Chaque utilisateur possède un Nom, Prénom, Email et l'accès aux projets associés.
    """
    first_name = models.CharField('Prénom', max_length=150, blank=False)
    last_name = models.CharField('Nom', max_length=150, blank=False)
    email = models.EmailField('Adresse e-mail', unique=True)

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.username

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username
