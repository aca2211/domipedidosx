from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction

phone_validator = RegexValidator(
    regex=r'^\+?\d{7,15}$',
    message='Ingresa un teléfono válido: solo números (7 a 15 dígitos) y un + opcional al inicio.',
)


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('cliente', 'Cliente'),
        ('operador', 'Operador de Sede'),
        ('cocina', 'Cocina'),
        ('repartidor', 'Repartidor'),
        ('admin', 'Administrador'),
    )
    # Roles que trabajan en una sede concreta y por tanto la necesitan.
    ROLES_CON_SEDE = ('operador', 'cocina')

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cliente')
    # blank=True para no romper cuentas existentes (p. ej. el superusuario);
    # el formulario de registro de clientes lo exige.
    phone = models.CharField('teléfono', max_length=16, blank=True, validators=[phone_validator])
    sede = models.ForeignKey(
        'menu.Sede', verbose_name='sede', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='personal',
        help_text='Sede donde trabaja (obligatoria para operador y cocina).',
    )

    def clean(self):
        super().clean()
        if self.role in self.ROLES_CON_SEDE and not self.sede_id:
            raise ValidationError({'sede': 'Los roles operador y cocina deben tener una sede asignada.'})

    def save(self, *args, **kwargs):
        # El rol da acceso al admin: operador entra (con permisos limitados en menu/admin.py)
        # y el administrador del sistema es superusuario. Solo se promueve, nunca se degrada.
        if self.role == 'admin':
            self.is_staff = self.is_superuser = True
        elif self.role == 'operador':
            self.is_staff = True
        super().save(*args, **kwargs)


class Direccion(models.Model):
    """Dirección de entrega guardada por un usuario (HU05)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='direcciones', on_delete=models.CASCADE
    )
    label = models.CharField('nombre', max_length=50, help_text='Ej: Casa, Trabajo')
    address = models.CharField('dirección', max_length=255)
    details = models.CharField('indicaciones', max_length=255, blank=True)
    latitude = models.DecimalField(
        'latitud', max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        'longitud', max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    is_default = models.BooleanField('principal', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'dirección'
        verbose_name_plural = 'direcciones'
        ordering = ['-is_default', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default=True),
                name='unica_direccion_principal_por_usuario',
            ),
        ]

    def __str__(self):
        return f'{self.label}: {self.address}'

    def save(self, *args, **kwargs):
        # Solo una dirección principal por usuario: al marcar esta, se desmarcan las demás.
        with transaction.atomic():
            if self.is_default:
                Direccion.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
            super().save(*args, **kwargs)
