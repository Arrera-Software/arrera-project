# 🔒 Rapport d'Audit de Sécurité — Arrera Project

**Date :** 2026-09-15
**Périmètre :** Application Django 5.1 (apps `accounts` et `projects`), configuration, templates, déploiement Docker/Compose, dépendances.
**Méthode :** Revue manuelle du code, `pip-audit` sur les dépendances, `manage.py check --deploy`, recherche de motifs XSS/CSRF/IDOR.

> ⚠️ Ce document liste des vulnérabilités **réelles ou potentielles** à des fins de correction. Classées par gravité.

---

## Résumé exécutif

| # | Vulnérabilité | Gravité | Type |
|---|---------------|---------|------|
| 1 | Dépendance Django vulnérable (7 CVE connues) | 🔴 Critique | Composants vulnérables |
| 2 | Mots de passe du « coffre-fort » stockés en clair | 🔴 Critique | Cryptographie |
| 3 | XSS stocké via le calendrier Gantt (`innerHTML`) | 🔴 Critique | XSS |
| 4 | Injection JS/XSS via `onclick` (mots de passe, URLs, logins) | 🔴 Critique | XSS |
| 5 | `SECRET_KEY` par défaut non sécurisée | 🔴 Critique | Configuration |
| 6 | `DEBUG=1` et `ALLOWED_HOSTS=*` par défaut | 🟠 Élevé | Configuration |
| 7 | Aucune limitation de tentatives de connexion (brute force) | 🟠 Élevé | Authentification |
| 8 | Upload de fichiers non validé (type/taille/contenu) | 🟠 Élevé | Upload / XSS stocké |
| 9 | Cookies sans `Secure`, pas de HTTPS forcé, pas de HSTS | 🟠 Élevé | Transport |
| 10 | Serveur de dev (`runserver`) en production, conteneur en root | 🟠 Élevé | Déploiement |
| 11 | Contrôle d'accès trop permissif sur les identifiants/tâches | 🟡 Moyen | Contrôle d'accès |
| 12 | Scripts CDN externes sans SRI (chaîne d'approvisionnement) | 🟡 Moyen | Intégrité |
| 13 | Port PostgreSQL exposé + mot de passe DB par défaut | 🟡 Moyen | Exposition réseau |
| 14 | Divers durcissements manquants | 🔵 Faible | Défense en profondeur |

---

## 🔴 Vulnérabilités critiques

### 1. Django 5.1.15 — 7 vulnérabilités connues
`requirements.txt` épingle `Django>=5.1,<5.2`, ce qui installe une version affectée par **7 CVE** (rapport `pip-audit`) :

```
PYSEC-2026-198 / 199 / 201   → corrigé en 5.2.15
PYSEC-2026-2090 / 2091 / 2092 → corrigé en 5.2.16
PYSEC-2026-3717              → corrigé en 5.2.17
```
La contrainte `<5.2` **empêche** d'installer les correctifs.

**Correction :** passer à une branche supportée et patchée, p. ex. `Django>=5.2.17,<5.3`, puis relancer `pip-audit` régulièrement (CI).

---

### 2. Mots de passe stockés en clair dans le « coffre-fort »
`projects/models.py` — `ProjectCredential.password = models.CharField(...)`. Les identifiants (SSH, bases de données, etc.) sont enregistrés **en texte clair** en base, renvoyés tels quels au template (`data-real="{{ cred.password }}"`, `templates/projects/subproject_detail.html:653`) et copiables. Un accès en lecture à la base (dump, sauvegarde, injection, admin compromis) expose tous les secrets des projets.

Le nom « coffre-fort sécurisé » (readme) est trompeur : il n'y a **aucun chiffrement**.

**Correction :** chiffrer au repos (ex. `cryptography.fernet` avec une clé hors base / KMS), ou déléguer à un vrai gestionnaire de secrets. Ne jamais renvoyer le secret en clair dans le HTML initial ; le charger via un endpoint dédié, journalisé et à accès restreint.

---

### 3. XSS stocké via le calendrier Gantt
`templates/projects/subproject_detail.html` :
- `L927 : const tasksGanttData = {{ tasks_gantt_json|safe }};`
- les données (`task.title`, `task.assigned_name`, `task.column_name`…) sont ensuite injectées via **`root.innerHTML`** (L1034, L1096–1160) **sans échappement**.

Tout membre d'un projet peut créer une tâche dont le titre est :
```html
<img src=x onerror="alert(document.cookie)">
```
Le code s'exécute dans le navigateur de **tous** les utilisateurs qui ouvrent l'onglet Gantt (vol de session, actions au nom de l'admin, etc.). Le `json.dumps` côté vue protège la structure JSON mais **pas** le rendu HTML fait en JS.

**Correction :** ne jamais construire le DOM par concaténation de chaînes. Utiliser `textContent`, `document.createElement`, ou échapper systématiquement chaque valeur avant insertion.

---

### 4. Injection JS via attributs `onclick`
Plusieurs valeurs contrôlées par l'utilisateur sont interpolées dans des gestionnaires d'événements inline :

```
subproject_detail.html:640  onclick="copyToClipboard('{{ cred.username }}', this)"
subproject_detail.html:662  onclick="copyToClipboard('{{ cred.password }}', this)"
subproject_detail.html:497  onclick="copyToClipboard('{{ res.target_url }}', this)"
project_detail.html:287     onclick="copyToClipboard('{{ res.target_url }}', this)"
```
L'auto-échappement Django transforme `'` en `&#x27;`, mais dans un attribut HTML le navigateur **décode** cette entité **avant** d'interpréter le JS. Une valeur comme :
```
'); alert(document.cookie); //
```
sort de la chaîne JavaScript et exécute du code arbitraire. Un mot de passe / login / URL malveillant devient donc un XSS stocké.

**Correction :** supprimer le JS inline ; utiliser des `data-*` attributs (auto-échappés correctement en contexte attribut) lus par un écouteur d'événement, ou appliquer un filtre `escapejs` **et** un contexte sûr. Idéalement, ajouter une CSP (`Content-Security-Policy`) qui interdit le JS inline.

---

### 5. `SECRET_KEY` de secours non sécurisée
`config/settings.py:16` :
```python
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-secret-key-fallback')
```
Si la variable d'environnement est absente (ex. `.env` oublié), l'application démarre **quand même** avec une clé publique et connue. Or la `SECRET_KEY` protège les signatures de session, les tokens CSRF, les cookies signés, les liens de réinitialisation… Une clé connue = sessions et tokens forgeables. `.env.example` propose aussi `SECRET_KEY=change-me-in-production`.

**Correction :** faire **échouer** le démarrage si `SECRET_KEY` n'est pas défini en production (pas de valeur de repli). Générer une clé aléatoire ≥ 50 caractères.

---

## 🟠 Vulnérabilités élevées

### 6. `DEBUG` et `ALLOWED_HOSTS` dangereux par défaut
`config/settings.py` :
```python
DEBUG = os.getenv('DEBUG', '1') == '1'                 # défaut = activé
ALLOWED_HOSTS = ... os.getenv('ALLOWED_HOSTS', '*') ... # défaut = tout
```
- `DEBUG=1` par défaut → pages d'erreur détaillées (traceback, settings, requêtes SQL) exposées en cas d'oubli de configuration.
- `ALLOWED_HOSTS=*` → aucune protection contre le *Host header poisoning*.
- `.env.example` fournit également `DEBUG=1`.

De plus, `config/urls.py:21-22` ne sert les médias **que** si `DEBUG` est vrai — signe que l'app est pensée pour tourner avec `DEBUG=1`.

**Correction :** défaut `DEBUG=0`, `ALLOWED_HOSTS` explicite obligatoire en production.

---

### 7. Aucune protection contre le brute-force
La vue de connexion (`accounts/views.py`) n'implémente **aucune** limitation de débit ni verrouillage de compte. Un template `templates/accounts/lockout.html` (« Sécurité Déclenchée », 15 min) existe mais **n'est jamais utilisé** : aucune dépendance type `django-axes` dans `requirements.txt`, aucune logique de comptage. C'est une protection **fictive**.

**Correction :** intégrer `django-axes` (ou équivalent), limiter les tentatives par IP + e-mail, et brancher réellement la page de lockout.

---

### 8. Upload de fichiers sans validation
`projects/forms.py` (`ProjectResourceForm`) et `resource_create_view` acceptent n'importe quel fichier : **aucun contrôle** d'extension, de type MIME ni de taille. Tout membre d'un projet peut téléverser :
- un fichier volumineux → **DoS disque** (aucune limite de taille) ;
- un `.svg` / `.html` malveillant → **XSS stocké** si les médias sont servis depuis le même domaine (les liens ouvrent `res.target_url` dans le navigateur) ;
- des noms de fichiers non assainis stockés tels quels comme titre.

**Correction :** liste blanche d'extensions/MIME, limite de taille (`DATA_UPLOAD_MAX_MEMORY_SIZE` + validation), servir les médias depuis un domaine séparé ou forcer `Content-Disposition: attachment`, régénérer les noms de fichiers.

---

### 9. Cookies non `Secure`, pas de HTTPS forcé, pas de HSTS
`manage.py check --deploy` remonte :
```
security.W004  SECURE_HSTS_SECONDS non défini
security.W008  SECURE_SSL_REDIRECT non True
security.W012  SESSION_COOKIE_SECURE non True
security.W016  CSRF_COOKIE_SECURE non True
```
Les cookies de session et CSRF peuvent transiter en clair (interception réseau / *session hijacking*). `HttpOnly` et `SameSite=Lax` sont bien positionnés (bon point), mais l'absence de `Secure` + HTTPS forcé annule une partie du bénéfice. `CSRF_TRUSTED_ORIGINS` est codé en dur en `http://` (localhost:8020).

**Correction :** en production `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_SSL_REDIRECT=True`, `SECURE_HSTS_SECONDS` (+ include subdomains/preload), et derrière un proxy `SECURE_PROXY_SSL_HEADER`.

---

### 10. Serveur de développement en production + conteneur root
- `Dockerfile:26` et `docker-compose.yml:22` lancent `python manage.py runserver 0.0.0.0:8000`. Le serveur de dev Django **n'est pas fait pour la production** (mono-thread, pas durci, non maintenu pour la charge/sécurité) alors que `gunicorn` est pourtant dans `requirements.txt`.
- Le conteneur tourne en **root** (aucun `USER` non privilégié dans le Dockerfile).
- `docker-compose.yml:24` monte tout le code source en volume (`.:/app:z`) — inadapté en prod.

**Correction :** servir via `gunicorn`/`uvicorn` derrière un reverse-proxy, créer un utilisateur non-root dans l'image, retirer le montage de volume et `WEB_PORT` de debug en prod.

---

## 🟡 Vulnérabilités moyennes

### 11. Contrôle d'accès trop large sur secrets et tâches
Dans `projects/views.py`, `credential_create_view`, `credential_delete_view`, `task_create_view`, `task_delete_view`, `task_move_view` et `resource_create_view` ne vérifient que `check_project_access` (**tout membre** du projet). Conséquences :
- N'importe quel membre simple peut **lire, ajouter et supprimer** les mots de passe du coffre-fort de tous les sous-projets du projet.
- N'importe quel membre peut supprimer les tâches des autres.

Ce n'est pas une IDOR classique (l'appartenance est vérifiée), mais l'absence de séparation des privilèges (membre vs chef de projet) sur des données sensibles est un risque. À confirmer selon l'intention métier.

**Correction :** restreindre la lecture/écriture des identifiants au chef de projet/admin, ou introduire des rôles ; journaliser les accès aux secrets.

---

### 12. Scripts CDN externes sans intégrité (SRI)
`templates/base.html` :
```html
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/@phosphor-icons/web"></script>
```
- Aucun attribut `integrity`/`crossorigin` → si le CDN est compromis, du JS arbitraire s'exécute sur l'app (chaîne d'approvisionnement).
- `cdn.tailwindcss.com` est explicitement **déconseillé en production** par Tailwind.

**Correction :** héberger les assets localement (build Tailwind, icônes en local) ou épingler avec SRI + versions figées.

---

### 13. Port PostgreSQL exposé + mot de passe DB par défaut
- `docker-compose.yml:13-14` publie `5432:5432` sur l'hôte → base accessible hors du réseau Docker.
- `config/settings.py:88` : `DB_PASSWORD` par défaut `'arrera_secret_password'` (valeur connue, dans le code source).

**Correction :** ne pas publier le port DB (le laisser interne au réseau compose), exiger un mot de passe fort via env sans valeur de repli.

---

## 🔵 Durcissements faibles / défense en profondeur

- **Pas de CSP** (`Content-Security-Policy`) : une CSP stricte limiterait fortement l'impact des XSS (#3, #4). `SECURE_BROWSER_XSS_FILTER`/`nosniff`/`X-Frame-Options=DENY` sont bien présents.
- **Énumération de comptes** : le backend d'auth mitige le *timing* (bon point, `accounts/backends.py`), mais `email unique` + messages permettent une énumération partielle ; garder un message générique (déjà le cas).
- **Durée de session** : 24 h sans expiration à la fermeture du navigateur (`SESSION_EXPIRE_AT_BROWSER_CLOSE=False`) — acceptable mais à ajuster pour des données sensibles.
- **`.env.example`** contient des mots de passe factices explicites (`change_this_password`) : s'assurer qu'aucun `.env` réel n'est jamais commité (il est bien dans `.gitignore`).
- **Absence de tests de sécurité** : `projects/tests.py` est vide ; ajouter des tests d'autorisation.

---

## Recommandations prioritaires (ordre d'action)

1. **Mettre à jour Django** vers ≥ 5.2.17 (#1) — corrige 7 CVE.
2. **Corriger les XSS** #3 et #4 (rendu DOM sûr + CSP).
3. **Chiffrer les secrets** du coffre-fort (#2).
4. **Durcir la configuration prod** : `SECRET_KEY` obligatoire, `DEBUG=0`, `ALLOWED_HOSTS`, cookies `Secure`/HTTPS/HSTS (#5, #6, #9).
5. **Valider les uploads** + **limiter le brute-force** (#7, #8).
6. **Déploiement** : gunicorn, conteneur non-root, port DB non exposé (#10, #13).

---

*Rapport généré lors d'une revue de sécurité manuelle assistée. Une revue applicative dynamique (DAST) et un test d'intrusion sur environnement déployé restent recommandés pour compléter cette analyse statique.*

---

# 🛠️ Plan de correction proposé

Voici, faille par faille, **ce que je propose de modifier concrètement** dans le code. Chaque bloc indique les fichiers touchés et l'approche. Rien n'est encore appliqué — c'est une proposition à valider ; dis-moi lesquels tu veux que je réalise (je recommande de commencer par le **Lot 1**).

## Lot 1 — Rapide & sans risque de régression (à faire en premier)

### #1 — Mettre à jour Django
- `requirements.txt` : remplacer `Django>=5.1,<5.2` par `Django>=5.2.17,<5.3`.
- Reconstruire l'image, relancer `pip-audit` et la suite de tests pour vérifier l'absence de régression (les changements 5.1 → 5.2 sont mineurs pour ce projet).

### #5 / #6 — Configuration sûre par défaut (`config/settings.py`)
- `SECRET_KEY` : supprimer la valeur de repli. Si `DEBUG=0` et pas de clé → **lever une erreur** au démarrage :
  ```python
  SECRET_KEY = os.getenv('SECRET_KEY')
  if not SECRET_KEY:
      if DEBUG:
          SECRET_KEY = 'django-insecure-dev-only'
      else:
          raise ImproperlyConfigured("SECRET_KEY manquant en production.")
  ```
- `DEBUG` : défaut à `0` (`os.getenv('DEBUG', '0') == '1'`).
- `ALLOWED_HOSTS` : pas de `*` par défaut ; défaut `localhost,127.0.0.1`, valeur explicite obligatoire en prod.
- `.env.example` : passer `DEBUG=0` et remplacer les exemples de secrets par des placeholders explicites.

### #9 — Cookies & transport (`config/settings.py`)
- Ajouter, pilotés par une variable d'env `SECURE=1` (activés en prod, désactivés en dev local) :
  ```python
  SESSION_COOKIE_SECURE = not DEBUG
  CSRF_COOKIE_SECURE = not DEBUG
  SECURE_SSL_REDIRECT = not DEBUG
  SECURE_HSTS_SECONDS = 31536000
  SECURE_HSTS_INCLUDE_SUBDOMAINS = True
  SECURE_HSTS_PRELOAD = True
  SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
  ```
- Rendre `CSRF_TRUSTED_ORIGINS` configurable via env plutôt que codé en dur en `http://`.

### #12 — CDN & CSP (`templates/base.html` + settings)
- Ajouter des en-têtes de sécurité, dont une **CSP** interdisant le JS inline (`django-csp` ou un middleware maison). Cela réduit fortement l'impact des XSS #3/#4.
- Épingler les scripts CDN à une version figée avec attribut `integrity` (SRI), ou — préférable — les héberger localement (build Tailwind + icônes Phosphor en local).

### #13 — Base de données (`docker-compose.yml` + settings)
- Retirer la publication du port `5432:5432` (garder la base interne au réseau Compose).
- `DB_PASSWORD` : supprimer la valeur de repli dans `settings.py` (exiger l'env).

## Lot 2 — Correctifs XSS (test manuel recommandé après)

### #3 — XSS Gantt (`templates/projects/subproject_detail.html`)
- Réécrire `renderGanttChart()` pour **ne plus concaténer** les données utilisateur dans `innerHTML`.
- Approche : construire la structure statique via template littéral, puis injecter chaque valeur dynamique (`task.title`, `assigned_name`, `column_name`) avec `textContent` / `createElement`, **ou** passer par une petite fonction `escapeHtml()` appliquée à toute valeur venant de `tasksGanttData`.

### #4 — Injection JS dans `onclick` (2 templates)
- Remplacer les `onclick="copyToClipboard('{{ ... }}', this)"` par des `data-*` attributs + un écouteur d'événement délégué :
  ```html
  <button class="copy-btn" data-copy="{{ cred.password }}">…</button>
  ```
  ```js
  document.addEventListener('click', e => {
    const b = e.target.closest('.copy-btn');
    if (b) copyToClipboard(b.dataset.copy, b);
  });
  ```
  (En contexte attribut, l'auto-échappement Django est sûr, contrairement au contexte JS inline.)
- Idem pour `toggleSecretReveal` et les `confirm(...)` contenant `{{ ... }}`.

## Lot 3 — Fonctionnel / demande arbitrage

### #2 — Chiffrer le coffre-fort (`projects/models.py`)
- Chiffrer `ProjectCredential.password` au repos via `cryptography.fernet`, la clé venant d'une variable d'env dédiée (`CREDENTIAL_ENCRYPTION_KEY`), **jamais** en base.
- Ne plus injecter le secret en clair dans le HTML initial (`data-real`) : le charger via un endpoint dédié, restreint et journalisé, au moment du « révéler ».
- ⚠️ Nécessite une **migration de données** (chiffrer l'existant). À planifier avec toi.

### #7 — Anti brute-force (`accounts/`)
- Ajouter `django-axes` dans `requirements.txt`, le configurer (verrou par IP + e-mail, 15 min) et **brancher réellement** `templates/accounts/lockout.html` (aujourd'hui inutilisé).

### #8 — Validation des uploads (`projects/forms.py`)
- Dans `ProjectResourceForm.clean_file()` : liste blanche d'extensions/MIME, taille maximale, et régénération/assainissement du nom de fichier.
- Ajouter `DATA_UPLOAD_MAX_MEMORY_SIZE` / `FILE_UPLOAD_MAX_MEMORY_SIZE` dans les settings.
- Servir les médias en `Content-Disposition: attachment` (ou domaine séparé) pour neutraliser un `.svg`/`.html` piégé.

### #10 — Déploiement (`Dockerfile`, `docker-compose.yml`)
- Remplacer `runserver` par `gunicorn config.wsgi` (déjà dans `requirements.txt`).
- Ajouter un utilisateur non-root (`USER appuser`) dans le `Dockerfile`.
- Retirer le montage de volume `.:/app` pour le service web en production.

### #11 — Séparation des privilèges (`projects/views.py`)
- **À arbitrer avec toi** (choix métier) : restreindre lecture/écriture/suppression des identifiants du coffre-fort au **chef de projet / admin** (`is_project_manager_or_admin`) plutôt qu'à tout membre, et/ou limiter la suppression de tâches à leur créateur ou au chef de projet.

---

## Ce que je te propose maintenant

- **Option A (recommandée)** : je réalise le **Lot 1** (mise à jour Django + durcissement config + CSP/CDN + DB), qui est rapide et à faible risque, puis on enchaîne sur le Lot 2 (XSS).
- **Option B** : je fais Lots 1 **et** 2 d'un coup (config + tous les XSS), qui traitent les critiques #3, #4, #5, #6.
- **Option C** : tu choisis des failles précises dans la liste.

Le **Lot 3** (chiffrement du coffre-fort, uploads, déploiement, privilèges) demande des décisions (migration de données, choix métier sur les rôles) — on le traitera après validation.

Dis-moi l'option et je commence.

---

# ✅ Corrections appliquées (2026-09-15)

**Toutes** les corrections des 3 lots ont été implémentées et validées. Résultats de vérification :
- `pip-audit` : **0 vulnérabilité** (contre 7).
- `manage.py check --deploy` : **0 problème** (contre 5 avertissements).
- Tests fonctionnels : chiffrement/déchiffrement OK, endpoint de révélation `200` pour l'admin / `403` pour un membre, upload `.svg` rejeté / `.pdf` accepté, restrictions du coffre-fort effectives.

| # | Faille | Statut | Fichiers modifiés |
|---|--------|--------|-------------------|
| 1 | Django vulnérable | ✅ Corrigé | `requirements.txt` → Django 5.2.17 |
| 2 | Secrets en clair | ✅ Corrigé | `projects/crypto.py`, `models.py`, `forms.py`, `views.py` (endpoint reveal), migration `0008`, template |
| 3 | XSS Gantt | ✅ Corrigé | `subproject_detail.html` (`escapeHtml` sur tout le rendu) |
| 4 | Injection JS `onclick` | ✅ Corrigé | `subproject_detail.html`, `project_detail.html` (data-* + écouteurs délégués) |
| 5 | `SECRET_KEY` de repli | ✅ Corrigé | `config/settings.py` (échec si absente en prod) |
| 6 | `DEBUG`/`ALLOWED_HOSTS` | ✅ Corrigé | `config/settings.py`, `.env.example` (défauts sûrs) |
| 7 | Brute-force | ✅ Corrigé | `django-axes` (settings, backends, middleware) + lockout branché |
| 8 | Uploads non validés | ✅ Corrigé | `forms.py` (`clean_file`), `settings.py` (limites de taille) |
| 9 | Cookies/HTTPS/HSTS | ✅ Corrigé | `config/settings.py` |
| 10 | runserver/root | ✅ Corrigé | `Dockerfile` (gunicorn + non-root), `docker-compose.yml`, WhiteNoise |
| 11 | Privilèges coffre-fort | ✅ Corrigé | `views.py` (coffre-fort réservé chef/admin ; suppression tâche = créateur/resp.) |
| 12 | CDN sans SRI | ⚠️ Atténué | CSP (`config/middleware.py`), version Phosphor épinglée |
| 13 | Port DB / mdp DB | ✅ Corrigé | `docker-compose.yml` (port non publié), `settings.py` (pas de repli) |
| 14 | Durcissements | ✅ Corrigé | CSP, Referrer-Policy, Permissions-Policy, journalisation des accès secrets |

## ⚠️ Actions manuelles requises avant mise en production

1. **Créer un `.env`** à partir de `.env.example` et renseigner :
   - `SECRET_KEY` (≥ 50 caractères aléatoires) ;
   - `CREDENTIAL_ENCRYPTION_KEY` (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) — **⚠️ à sauvegarder : sans elle, les secrets du coffre-fort deviennent illisibles** ;
   - `DB_PASSWORD` fort, `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` réels ;
   - `DEBUG=0`.
2. **Appliquer les migrations** (`./migrate.sh` ou `manage.py migrate`) : la migration `0008` chiffre les mots de passe déjà en base.
3. **Terminer TLS** au niveau du reverse-proxy (les redirections HTTPS/HSTS sont activées hors DEBUG).
4. **Restrictions notées** : `#12` reste une atténuation (CSP + version épinglée) ; pour une protection complète, héberger Tailwind/Phosphor localement avec intégrité (SRI).

## Notes techniques
- Nouveau champ `Task.created_by` (migration `0007`) : nécessaire au contrôle de suppression des tâches (l'ancien code l'assignait sans qu'il existe en base).
- Le coffre-fort n'expose plus jamais le secret dans le HTML : il est récupéré à la demande via `POST /projets/credentials/<id>/reveal/`, avec contrôle d'accès et journalisation (`logger projects.credentials`).
- WhiteNoise a été ajouté pour servir les fichiers statiques une fois `DEBUG=0` (sinon l'app perdrait tout son style) ; `collectstatic` est lancé au démarrage du conteneur web.
