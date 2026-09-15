from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailAuthBackend(ModelBackend):
    """
    Backend d'authentification strict par adresse e-mail.
    Ne permet la connexion qu'en fournissant l'adresse e-mail exacte du compte.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get('email', username)
        if not email or not password:
            return None

        email = email.strip().lower()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Mitigation contre les attaques par canal auxiliaire / timing attack
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=email).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
