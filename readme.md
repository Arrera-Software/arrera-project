# Arrera Project

Plateforme moderne de gestion de projets et de sous-projets pour Arrera.

---

## 🎨 Icône du projet (Favicon & Header)

Pour intégrer votre logo/icône personnalisée dans toute l'application (onglet de navigation, en-tête et page de connexion) :

1. Placez votre fichier dans le dossier :
   ```
   static/img/
   ```
2. Nommez votre fichier selon votre format préféré :
   - **`static/img/icon.svg`** *(Recommandé : vectoriel, ultra-net à toutes les résolutions)*
   - **`static/img/icon.png`** *(Alternative haute résolution)*

---

## 🚀 Fonctionnalités principales

- **Vue Projets & Administration** :
  - Création de projets réservée à l'administrateur.
  - Attribution d'un **Chef de projet** avec tous les droits de gestion.
  - Gestion des membres de l'équipe assignés.
- **Structure par Sous-projets** :
  - Chaque projet peut être découpé en plusieurs sous-projets indépendants.
  - **5 onglets dédiés par sous-projet** :
    1. **Général** : Tableau Kanban de l'ensemble des tâches de l'équipe.
    2. **Personnel** : Vue filtrée sur les tâches assignées à l'utilisateur connecté.
    3. **Planning Gantt** : Calendrier Timeline interactif avec visualisation des dates limites (deadlines) et statuts.
    4. **Docs & Fichiers** : Téléversement direct de fichiers physiques (*PDF, archives ZIP, tableurs, images*) et centralisation de liens web (*Figma, Google Docs, Notion, dépôts Git*).
    5. **Mots de passe** : Coffre-fort sécurisé des accès, clés et identifiants.

---

## 🛠️ Stack Technique

- **Backend** : Django 5 (Python 3.13)
- **Base de données** : PostgreSQL 16
- **Interface & Design** : HTML5, Tailwind CSS, Thème Arrera Adwaita / Material You Dark & Light
- **Conteneurisation** : Podman / Docker

---

## 💻 Commandes utiles

- **Démarrer l'application** :
  ```bash
  ./start.sh
  ```
  Accessible sur : [http://localhost:8020](http://localhost:8020)
- **Appliquer les migrations** :
  ```bash
  ./migrate.sh
  ```
- **Créer / Réinitialiser le superutilisateur** :
  ```bash
  ./createsuperuser.sh
  ```
- **Arrêter les conteneurs** :
  ```bash
  ./stop.sh
  ```
