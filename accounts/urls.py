from django.urls import path
from .views import CustomLoginView, CustomLogoutView, dashboard_view

urlpatterns = [
    path('', dashboard_view, name='home'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
]
