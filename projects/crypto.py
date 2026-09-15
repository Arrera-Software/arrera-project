"""
Chiffrement symétrique des secrets du coffre-fort (ProjectCredential).

Utilise Fernet (AES-128-CBC + HMAC) de la bibliothèque `cryptography`.
La clé provient de settings.CREDENTIAL_ENCRYPTION_KEY si définie ; sinon elle
est dérivée de SECRET_KEY (acceptable en développement, à fixer explicitement
en production pour permettre la rotation indépendante de la SECRET_KEY).

Les valeurs chiffrées sont préfixées par `enc:` afin de distinguer, lors des
migrations, un secret déjà chiffré d'un ancien secret en clair.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

ENC_PREFIX = "enc:"


def _get_fernet():
    key = getattr(settings, 'CREDENTIAL_ENCRYPTION_KEY', '') or ''
    if key:
        # Clé Fernet fournie telle quelle (44 caractères base64 urlsafe).
        key_bytes = key.encode()
    else:
        # Dérivation déterministe depuis SECRET_KEY (dev / repli).
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key_bytes = base64.urlsafe_b64encode(digest)
    return Fernet(key_bytes)


def encrypt(plaintext: str) -> str:
    """Chiffre une chaîne. Renvoie une valeur préfixée `enc:`."""
    if plaintext is None:
        plaintext = ""
    token = _get_fernet().encrypt(plaintext.encode())
    return ENC_PREFIX + token.decode()


def decrypt(value: str) -> str:
    """
    Déchiffre une valeur produite par encrypt().
    Par tolérance, une valeur non préfixée (ancien secret en clair non encore
    migré) est renvoyée telle quelle.
    """
    if not value:
        return ""
    if not value.startswith(ENC_PREFIX):
        return value  # ancienne donnée en clair
    token = value[len(ENC_PREFIX):].encode()
    try:
        return _get_fernet().decrypt(token).decode()
    except InvalidToken:
        return ""


def is_encrypted(value: str) -> bool:
    return bool(value) and value.startswith(ENC_PREFIX)
