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

echo "===> Création des migrations (makemigrations)..."
$COMPOSE_CMD exec web python manage.py makemigrations

echo "===> Application des migrations (migrate)..."
$COMPOSE_CMD exec web python manage.py migrate

echo "===> Migrations terminées avec succès !"
