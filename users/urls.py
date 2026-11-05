from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .forms import LoginForm

urlpatterns = [
    path('', views.home, name='home'),
    path('registro/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(authentication_form=LoginForm), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Perfil y direcciones del cliente (HU05)
    path('perfil/', views.perfil, name='perfil'),
    path('direcciones/', views.direccion_lista, name='direccion_lista'),
    path('direcciones/nueva/', views.direccion_crear, name='direccion_crear'),
    path('direcciones/<int:pk>/editar/', views.direccion_editar, name='direccion_editar'),
    path('direcciones/<int:pk>/eliminar/', views.direccion_eliminar, name='direccion_eliminar'),
    path('direcciones/<int:pk>/principal/', views.direccion_principal, name='direccion_principal'),
]
