# Arrera Project

Création d'une interface de gestion de projet pour les projets d'Arrera.

## Composition

- **Page d'accueil** : Vue d'ensemble où les utilisateurs voient chaque projet.
- **Page de projet** :
  - **Vue Kanban générale** : Visualisation de toutes les tâches en cours pour l'ensemble des collaborateurs.
  - **Vue Kanban personnelle** : Visualisation des tâches personnelles à faire.
  - **Gestionnaire de mots de passe intégré** : Stockage et consultation des mots de passe importants pour chaque projet.

## Stack Technique

- **Backend** : Django (Python 3.14)
- **Base de données** : PostgreSQL 16
- **Conteneurisation** : Podman / Docker

## Commandes utiles

- **Démarrer l'application** : `./start.sh` (accessible sur `http://localhost:8020`)
- **Appliquer les migrations** : `./migrate.sh`
- **Créer / Réinitialiser l'admin** : `./createsuperuser.sh`
- **Arrêter les conteneurs** : `./stop.sh`
