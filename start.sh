#!/usr/bin/env bash
set -e

# Détection de l'outil compose (podman compose, podman-compose ou docker compose)
if command -v podman &>/dev/null && podman compose version &>/dev/null; then
    COMPOSE_CMD="podman compose"
elif command -v podman-compose &>/dev/null; then
    COMPOSE_CMD="podman-compose"
elif command -v docker &>/dev/null && docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "Erreur : Aucun outil Compose trouvé (podman compose, podman-compose ou docker compose)."
    exit 1
fi

echo "===> Démarrage des conteneurs avec $COMPOSE_CMD..."
$COMPOSE_CMD up --build -d

echo "===> Services démarrés !"
echo "===> Application accessible sur http://localhost:${WEB_PORT:-8020}"
