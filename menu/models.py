from datetime import time

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.conf import settings


class Sede(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    opening_time = models.TimeField('hora de apertura', default=time(10, 0))
    closing_time = models.TimeField('hora de cierre', default=time(22, 0))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def is_open_at(self, hora):
        """True si la sede atiende a esa hora. Soporta horarios que cruzan la medianoche."""
        if self.opening_time <= self.closing_time:
            return self.opening_time <= hora < self.closing_time
        return hora >= self.opening_time or hora < self.closing_time

    def is_open_now(self):
        return self.is_open_at(timezone.localtime().time())


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    sedes = models.ManyToManyField(Sede, through='SedeProduct', related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField('imagen', upload_to='products/', blank=True)
    prep_time_minutes = models.PositiveSmallIntegerField(
        'tiempo de preparación (min)', default=15,
        validators=[MinValueValidator(1), MaxValueValidator(240)],
    )

    def __str__(self):
        return self.name


class SedeProduct(models.Model):
    """Disponibilidad de un producto en una sede (HU11).
    Más adelante recibirá stock y stock mínimo (HU29, HU30)."""
    sede = models.ForeignKey(Sede, related_name='sede_products', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='sede_products', on_delete=models.CASCADE)
    is_available = models.BooleanField('disponible', default=True)

    class Meta:
        verbose_name = 'producto por sede'
        verbose_name_plural = 'productos por sede'
        constraints = [
            models.UniqueConstraint(fields=['sede', 'product'], name='unico_producto_por_sede'),
        ]

    def __str__(self):
        return f'{self.product} en {self.sede}'


class ProductOption(models.Model):
    """Opción de personalización de un producto (HU10): tamaño, adición o ingrediente excluible.

    - Tamaño: el cliente elige uno; el recargo se suma al precio base del producto.
    - Adición: el cliente puede elegir varias; cada una suma su recargo.
    - Exclusión: ingrediente que el cliente puede quitar; no cambia el precio.
    """
    SIZE = 'size'
    ADDON = 'addon'
    EXCLUSION = 'exclusion'
    KIND_CHOICES = [
        (SIZE, 'Tamaño'),
        (ADDON, 'Adición'),
        (EXCLUSION, 'Ingrediente excluible'),
    ]

    product = models.ForeignKey(Product, related_name='options', on_delete=models.CASCADE)
    kind = models.CharField('tipo', max_length=10, choices=KIND_CHOICES)
    name = models.CharField('nombre', max_length=100)
    extra_price = models.DecimalField(
        'recargo', max_digits=8, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
        help_text='Se suma al precio base. Las exclusiones no llevan recargo.',
    )
    is_active = models.BooleanField('activa', default=True)

    class Meta:
        verbose_name = 'opción de producto'
        verbose_name_plural = 'opciones de producto'
        ordering = ['kind', 'extra_price', 'name']
        constraints = [
            models.UniqueConstraint(fields=['product', 'kind', 'name'], name='unica_opcion_por_producto'),
        ]

    def __str__(self):
        return f'{self.get_kind_display()}: {self.name} ({self.product})'

    def clean(self):
        super().clean()
        if self.kind == self.EXCLUSION and self.extra_price:
            raise ValidationError({'extra_price': 'Un ingrediente excluible no puede tener recargo.'})
