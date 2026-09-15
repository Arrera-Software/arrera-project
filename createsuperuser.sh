#!/usr/bin/env bash
set -e

if command -v podman &>/dev/null && podman compose version &>/dev/null; then
    COMPOSE_CMD="podman compose"
elif command -v podman-compose &>/dev/null; then
    COMPOSE_CMD="podman-compose"
elif command -v docker &>/dev/null && docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "Erreur : Aucun outil Compose trouvé."
    exit 1
fi

echo "===> Création / Réinitialisation du superutilisateur Django..."

# Exécute un script python dans le conteneur pour créer ou réinitialiser le mot de passe de l'admin
$COMPOSE_CMD exec web python manage.py shell -c "
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@arrera.local')
password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'adminpassword')

user, created = User.objects.get_or_create(username=username, defaults={'email': email})
user.set_password(password)
user.is_staff = True
user.is_superuser = True
user.save()

if created:
    print(f'Superutilisateur \"{username}\" créé avec succès !')
else:
    print(f'Superutilisateur \"{username}\" existant mis à jour (mot de passe réinitialisé) !')
"
