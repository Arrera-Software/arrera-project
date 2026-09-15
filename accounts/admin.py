from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm

# Désinscription du modèle Group par défaut (inutile dans notre architecture)
admin.site.unregister(Group)

# Restriction stricte de l'accès au panneau d'administration Django aux seuls superutilisateurs
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser
admin.site.site_header = "Arrera Project - Administration"
admin.site.site_title = "Arrera Admin"
admin.site.index_title = "Gestion globale du système"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ('username', 'first_name', 'last_name', 'email', 'is_superuser', 'is_active')
    list_filter = ('is_superuser', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('last_name', 'first_name')

    # Suppression des Groupes et Permissions granulaires
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'email')}),
        ('Statut du compte', {
            'fields': ('is_active', 'is_superuser'),
            'description': "Cochez 'Superutilisateur' pour accorder les droits d'administration complets (création de projets, accès admin)."
        }),
        ('Historique', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'email', 'password1', 'password2'),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Si l'utilisateur est superutilisateur, il est automatiquement staff pour accéder à l'admin
        obj.is_staff = obj.is_superuser
        super().save_model(request, obj, form, change)
