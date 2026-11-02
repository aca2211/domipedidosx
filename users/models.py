from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('cliente', 'Cliente'),
        ('operador', 'Operador de Sede'),
        ('cocina', 'Cocina'),
        ('repartidor', 'Repartidor'),
        ('admin', 'Administrador'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cliente')
