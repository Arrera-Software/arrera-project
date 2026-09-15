from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import authenticate
from .models import User


class CustomUserCreationForm(UserCreationForm):
    """Formulaire de création d'un utilisateur dans l'admin Django."""
    first_name = forms.CharField(label="Prénom", max_length=150, required=True)
    last_name = forms.CharField(label="Nom", max_length=150, required=True)
    email = forms.EmailField(label="Adresse e-mail", required=True)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')


class CustomUserChangeForm(UserChangeForm):
    """Formulaire de modification d'un utilisateur dans l'admin Django."""
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser')


class LoginForm(forms.Form):
    """
    Formulaire de connexion strict par adresse e-mail.
    Bloque toute tentative utilisant un identifiant textuel classique.
    """
    email = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.EmailInput(attrs={
            'placeholder': 'nom@exemple.com',
            'autocomplete': 'email',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'placeholder': '••••••••••••',
            'autocomplete': 'current-password',
        })
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(
                self.request,
                username=email,
                email=email,
                password=password
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    "Adresse e-mail ou mot de passe incorrect.",
                    code='invalid_login'
                )
            elif not self.user_cache.is_active:
                raise forms.ValidationError(
                    "Ce compte est désactivé. Veuillez contacter un administrateur.",
                    code='inactive'
                )
        return cleaned_data

    def get_user(self):
        return self.user_cache
