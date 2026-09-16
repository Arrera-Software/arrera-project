from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LogoutView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.db.models import Q
from .forms import LoginForm
from projects.models import Project


@method_decorator(csrf_protect, name='dispatch')
@method_decorator(never_cache, name='dispatch')
class CustomLoginView(FormView):
    """
    Vue de connexion personnalisée avec sécurité renforcée.
    - Connexion STRICTEMENT par adresse e-mail.
    """
    template_name = 'accounts/login.html'
    form_class = LoginForm
    success_url = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        user = form.get_user()
        auth_login(self.request, user)
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    """Déconnexion sécurisée de l'utilisateur."""
    next_page = reverse_lazy('login')


@login_required
def dashboard_view(request):
    """
    Page d'accueil après connexion.
    - Superutilisateur : voit l'ensemble des projets créés.
    - Utilisateur standard : voit les projets dont il est membre ou chef de projet.
    """
    if request.user.is_superuser:
        projects = Project.objects.prefetch_related('members', 'subprojects', 'manager').all()
    else:
        projects = Project.objects.filter(
            Q(members=request.user) | Q(manager=request.user)
        ).distinct().prefetch_related('members', 'subprojects', 'manager')

    return render(request, 'home.html', {
        'user': request.user,
        'projects': projects,
    })
