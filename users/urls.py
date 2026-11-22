from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views
from .forms import LoginForm, NuevaContrasenaForm, RecuperarContrasenaForm

urlpatterns = [
    path('', views.home, name='home'),
    path('registro/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(authentication_form=LoginForm), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Recuperar contraseña (HU03)
    path('recuperar/', auth_views.PasswordResetView.as_view(
        form_class=RecuperarContrasenaForm,
        email_template_name='registration/password_reset_email.txt',
        subject_template_name='registration/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done'),
    ), name='password_reset'),
    path('recuperar/enviado/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('recuperar/completo/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('recuperar/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        form_class=NuevaContrasenaForm,
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    # Perfil y direcciones del cliente (HU05)
    path('perfil/', views.perfil, name='perfil'),
    path('direcciones/', views.direccion_lista, name='direccion_lista'),
    path('direcciones/nueva/', views.direccion_crear, name='direccion_crear'),
    path('direcciones/<int:pk>/editar/', views.direccion_editar, name='direccion_editar'),
    path('direcciones/<int:pk>/eliminar/', views.direccion_eliminar, name='direccion_eliminar'),
    path('direcciones/<int:pk>/principal/', views.direccion_principal, name='direccion_principal'),
]
