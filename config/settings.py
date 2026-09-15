"""
Django settings for arrera-project.
"""

from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: don't run with debug turned on in production!
# Défaut sûr : DEBUG désactivé sauf demande explicite.
DEBUG = os.getenv('DEBUG', '0') == '1'

# SECURITY WARNING: keep the secret key used in production secret!
# Aucune valeur de repli en production : l'application refuse de démarrer
# sans SECRET_KEY explicite. En développement (DEBUG=1) une clé jetable est tolérée.
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-only-do-not-use-in-production'
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY est obligatoire en production. Définissez la variable "
            "d'environnement SECRET_KEY (>= 50 caractères aléatoires)."
        )

# Allowed hosts : pas de '*' par défaut. Valeur explicite attendue en production.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if host.strip()
]

# CSRF Trusted Origins configurables via l'environnement (aucune valeur http codée en dur).
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost:8020,http://127.0.0.1:8020',
    ).split(',')
    if origin.strip()
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Sécurité : protection anti-brute-force
    'axes',
    # Apps du projet
    'accounts',
    'projects',
]

# Modèle Utilisateur personnalisé
AUTH_USER_MODEL = 'accounts.User'

# Authentification stricte par e-mail.
# AxesStandaloneBackend doit être en tête pour intercepter les tentatives verrouillées.
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'accounts.backends.EmailAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Service des fichiers statiques en production (sans DEBUG)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # En-têtes de sécurité supplémentaires (CSP, Referrer-Policy, Permissions-Policy)
    'config.middleware.SecurityHeadersMiddleware',
    # AxesMiddleware doit être placé en dernier.
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database configuration (PostgreSQL via env vars ou SQLite fallback)
DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.postgresql')
DB_NAME = os.getenv('DB_NAME', 'arrera_db')
DB_USER = os.getenv('DB_USER', 'arrera_user')
# Aucun mot de passe par défaut dans le code source : il doit venir de l'environnement.
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'db')
DB_PORT = os.getenv('DB_PORT', '5432')

if os.getenv('USE_SQLITE', '0') == '1':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    if not DEBUG and not DB_PASSWORD:
        raise ImproperlyConfigured(
            "DB_PASSWORD est obligatoire en production. Définissez la variable "
            "d'environnement DB_PASSWORD."
        )
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Redirections d'authentification
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'

# Sécurité des Cookies & Sessions
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 86400  # 24 heures
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'

# HTTPS forcé, cookies Secure et HSTS : activés hors développement.
# Derrière un reverse-proxy TLS, on lit l'en-tête X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000  # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Limites de téléversement (défense contre le DoS disque / mémoire)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 Mo pour le corps de requête
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 Mo avant bascule sur disque
# Taille maximale acceptée pour un fichier téléversé (validée dans ProjectResourceForm)
MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', str(25 * 1024 * 1024)))  # 25 Mo

# --- Protection anti-brute-force (django-axes) ---
AXES_FAILURE_LIMIT = int(os.getenv('AXES_FAILURE_LIMIT', '5'))
AXES_COOLOFF_TIME = 0.25  # 15 minutes (0,25 heure)
AXES_LOCKOUT_TEMPLATE = 'accounts/lockout.html'
AXES_RESET_ON_SUCCESS = True
# Verrou combiné IP + identifiant (l'e-mail est passé comme "username")
AXES_LOCKOUT_PARAMETERS = [['ip_address', 'username']]

# --- Chiffrement du coffre-fort de mots de passe (ProjectCredential) ---
# Clé Fernet dédiée. À défaut, une clé est dérivée de SECRET_KEY (suffisant en dev,
# à définir explicitement en production pour permettre la rotation).
CREDENTIAL_ENCRYPTION_KEY = os.getenv('CREDENTIAL_ENCRYPTION_KEY', '')

# Internationalization
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Stockage : WhiteNoise pour servir les statiques compressés en production.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Media files (Téléversement de fichiers de projets)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Journalisation (accès aux secrets du coffre-fort notamment)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'projects.credentials': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
