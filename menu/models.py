from datetime import time

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


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
    sede = models.ManyToManyField(Sede, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField('imagen', upload_to='products/', blank=True)
    prep_time_minutes = models.PositiveSmallIntegerField(
        'tiempo de preparación (min)', default=15,
        validators=[MinValueValidator(1), MaxValueValidator(240)],
    )
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.name
