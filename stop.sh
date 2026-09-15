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

echo "===> Arrêt des conteneurs..."
$COMPOSE_CMD down
echo "===> Conteneurs arrêtés."
