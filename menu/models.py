import re
import unicodedata
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

    def is_open_at_datetime(self, momento):
        """True si la sede atiende en ese momento: no es feriado y está dentro del horario (HU38)."""
        if Feriado.es_feriado(momento.date()):
            return False
        return self.is_open_at(momento.time())

    def is_open_now(self):
        return self.is_open_at_datetime(timezone.localtime())


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


class StockInsuficiente(Exception):
    """Se pidieron más unidades de las que hay en existencias (HU29)."""
    def __init__(self, sede_product):
        self.sede_product = sede_product
        super().__init__(str(sede_product))


class SedeProduct(models.Model):
    """Disponibilidad y existencias de un producto en una sede (HU11, HU29, HU30)."""
    sede = models.ForeignKey(Sede, related_name='sede_products', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='sede_products', on_delete=models.CASCADE)
    is_available = models.BooleanField('disponible', default=True)
    stock = models.PositiveIntegerField(
        'existencias', null=True, blank=True,
        help_text='Unidades en inventario. Vacío = sin control de existencias.',
    )
    stock_minimo = models.PositiveIntegerField(
        'stock mínimo', default=0,
        help_text='Cuando las existencias llegan a este número, el operador recibe una alerta para reponer.',
    )

    class Meta:
        verbose_name = 'producto por sede'
        verbose_name_plural = 'productos por sede'
        constraints = [
            models.UniqueConstraint(fields=['sede', 'product'], name='unico_producto_por_sede'),
        ]

    def __str__(self):
        return f'{self.product} en {self.sede}'

    def save(self, *args, **kwargs):
        # HU29: sin existencias el producto se bloquea solo, para que el menú y el carrito lo oculten
        if self.stock == 0:
            self.is_available = False
        super().save(*args, **kwargs)

    @property
    def bajo_minimo(self):
        """True si hay control de existencias y estamos en el mínimo o por debajo (HU30)."""
        return self.stock is not None and self.stock <= self.stock_minimo

    def descontar(self, cantidad):
        if self.stock is None:
            return
        if cantidad > self.stock:
            raise StockInsuficiente(self)
        self.stock -= cantidad
        self.save()

    def reponer(self, cantidad):
        if self.stock is None:
            return
        estaba_agotado = self.stock == 0
        self.stock += cantidad
        if estaba_agotado and self.stock > 0:
            self.is_available = True
        self.save()


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


class Feriado(models.Model):
    """Día festivo en el que ninguna sede recibe pedidos (HU38). Se registra desde el admin."""
    date = models.DateField('fecha', unique=True)
    name = models.CharField('nombre', max_length=100)

    class Meta:
        verbose_name = 'feriado'
        verbose_name_plural = 'feriados'
        ordering = ['date']

    def __str__(self):
        return f'{self.name} ({self.date:%d/%m/%Y})'

    @classmethod
    def es_feriado(cls, fecha):
        return cls.objects.filter(date=fecha).exists()


class ParametrosGlobales(models.Model):
    """Configuración global del sistema, una sola fila (HU38).

    Se lee con ParametrosGlobales.cargar(); si no existe, se crea con los valores por defecto.
    """
    margen_entrega_minutos = models.PositiveSmallIntegerField(
        'margen de entrega (min)', default=10,
        validators=[MaxValueValidator(120)],
        help_text='Minutos extra que se suman al tiempo estimado de entrega.',
    )
    pedido_minimo_global = models.DecimalField(
        'pedido mínimo global', max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
        help_text='Mínimo de pedido cuando una zona no define uno propio. 0 = sin mínimo.',
    )

    class Meta:
        verbose_name = 'parámetros globales'
        verbose_name_plural = 'parámetros globales'

    def __str__(self):
        return 'Parámetros globales'

    def save(self, *args, **kwargs):
        self.pk = 1   # una sola fila
        super().save(*args, **kwargs)

    @classmethod
    def cargar(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

# ---------------------------------------------------------------------------
# HU26: Tope de pedidos por sede y franja horaria
# ---------------------------------------------------------------------------

class TopeCapacidad(models.Model):
    """Límite de pedidos que acepta la cocina de una sede en una franja del día (HU26).

    La verificación usa `vigente()` justo antes de crear el pedido, dentro de
    la misma transacción atómica, para que dos pedidos concurrentes no puedan
    superar el tope al mismo tiempo.
    """
    sede = models.ForeignKey(
        Sede, related_name='topes', on_delete=models.CASCADE,
    )
    hora_inicio = models.TimeField('hora de inicio')
    hora_fin    = models.TimeField('hora de fin')
    max_pedidos = models.PositiveSmallIntegerField(
        'máximo de pedidos',
        validators=[MinValueValidator(1)],
        help_text='Pedidos activos que acepta la cocina en la franja. Los pedidos cancelados no cuentan.',
    )
    umbral_alerta = models.PositiveSmallIntegerField(
        'umbral de alerta (%)', default=80,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Al alcanzar este porcentaje del tope se muestra la alerta al operador.',
    )
    is_active = models.BooleanField('activo', default=True)

    class Meta:
        verbose_name = 'tope de capacidad'
        verbose_name_plural = 'topes de capacidad'
        ordering = ['sede', 'hora_inicio']

    def __str__(self):
        return f'{self.sede}: {self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M} (máx. {self.max_pedidos})'

    def clean(self):
        super().clean()
        if not (self.hora_inicio and self.hora_fin):
            return
        if self.hora_inicio >= self.hora_fin:
            raise ValidationError({'hora_fin': 'La hora de fin debe ser posterior a la de inicio.'})
        if self.is_active and self.sede_id:
            solapados = TopeCapacidad.objects.filter(
                sede_id=self.sede_id,
                is_active=True,
                hora_inicio__lt=self.hora_fin,
                hora_fin__gt=self.hora_inicio,
            ).exclude(pk=self.pk)
            if solapados.exists():
                raise ValidationError('Esta franja se cruza con otra franja activa de la misma sede.')

    @classmethod
    def vigente(cls, sede, hora):
        """Tope activo de la sede para esa hora, o None si no hay tope configurado."""
        return cls.objects.filter(
            sede=sede,
            is_active=True,
            hora_inicio__lte=hora,
            hora_fin__gt=hora,
        ).first()


# ---------------------------------------------------------------------------
# HU24: Zonas de cobertura con tarifa, tiempo estimado y pedido mínimo
# ---------------------------------------------------------------------------

def normalizar(texto):
    """Minúsculas, sin tildes y sin signos: «Calle 5 # 38-10, Barrio San Fernando» -> «calle 5 38 10 barrio san fernando»."""
    sin_tildes = ''.join(
        c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn'
    )
    return ' '.join(re.findall(r'[a-z0-9]+', sin_tildes.casefold()))


class ZonaCobertura(models.Model):
    """Zona de una sede donde se entregan domicilios (HU24).

    La zona se define con una lista de barrios. Una dirección pertenece a la zona si el
    nombre de alguno de sus barrios aparece en el texto de la dirección (HU25 usa esto
    para rechazar las direcciones que no caen en ninguna zona).

    Si una sede no tiene zonas activas, no se restringe ni se cobra domicilio por zona.
    """
    sede = models.ForeignKey(Sede, related_name='zonas', on_delete=models.CASCADE)
    nombre = models.CharField('nombre de la zona', max_length=100, help_text='Ej: Zona 1 - Cercana')
    barrios = models.TextField(
        help_text='Un barrio por línea (o separados por comas). Ej: Granada, San Fernando, Centenario.',
    )
    tarifa_domicilio = models.DecimalField(
        'tarifa de domicilio', max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    tiempo_estimado_min = models.PositiveSmallIntegerField(
        'tiempo estimado de entrega (min)', default=30,
        validators=[MinValueValidator(1), MaxValueValidator(240)],
        help_text='Minutos de entrega para esta zona (lo usa el cálculo del tiempo estimado, HU32).',
    )
    pedido_minimo = models.DecimalField(
        'pedido mínimo', max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text='Vacío = usa el pedido mínimo global. 0 = sin mínimo en esta zona.',
    )
    is_active = models.BooleanField('activa', default=True)

    class Meta:
        verbose_name = 'zona de cobertura'
        verbose_name_plural = 'zonas de cobertura'
        ordering = ['sede', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['sede', 'nombre'], name='unica_zona_por_sede'),
        ]

    def __str__(self):
        return f'{self.sede} · {self.nombre}'

    @property
    def lista_barrios(self):
        """Los barrios de la zona como lista de textos (sin vacíos)."""
        return [b.strip() for b in re.split(r'[\n,;]+', self.barrios or '') if b.strip()]

    def _barrios_normalizados(self):
        return [n for n in (normalizar(b) for b in self.lista_barrios) if n]

    def clean(self):
        super().clean()
        nuevos = set(self._barrios_normalizados())
        if not nuevos:
            raise ValidationError({'barrios': 'Escribe al menos un barrio.'})
        if self.is_active and self.sede_id:
            otras = ZonaCobertura.objects.filter(sede_id=self.sede_id, is_active=True).exclude(pk=self.pk)
            for otra in otras:
                repetidos = nuevos & set(otra._barrios_normalizados())
                if repetidos:
                    raise ValidationError({
                        'barrios': f'El barrio «{sorted(repetidos)[0]}» ya está en la zona «{otra.nombre}» de esta sede.',
                    })

    def coincidencia(self, texto):
        """Largo del barrio más largo de la zona que aparece en el texto; 0 si ninguno aparece."""
        destino = f' {normalizar(texto)} '
        return max((len(b) for b in self._barrios_normalizados() if f' {b} ' in destino), default=0)

    def minimo_efectivo(self):
        """Pedido mínimo de la zona; si no define uno, el global (HU38)."""
        if self.pedido_minimo is not None:
            return self.pedido_minimo
        return ParametrosGlobales.cargar().pedido_minimo_global

    @classmethod
    def tiene_zonas(cls, sede):
        return cls.objects.filter(sede=sede, is_active=True).exists()

    @classmethod
    def para_direccion(cls, sede, direccion):
        """Zona activa de la sede que cubre la dirección, o None. Si varias coinciden, gana el barrio más específico."""
        mejor, mejor_largo = None, 0
        for zona in cls.objects.filter(sede=sede, is_active=True):
            largo = zona.coincidencia(direccion.address)
            if largo > mejor_largo:
                mejor, mejor_largo = zona, largo
        return mejor
