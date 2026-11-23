from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.conf import settings

class Pedido(models.Model):
    ESTADOS =[('recibido', 'Recibido'), ('en_preparacion', 'En preparacion'), ('listo', 'Listo'), ('entregado', 'Entregado'), ('cancelado', 'Cancelado')]
    METODOS_PAGO =[('efectivo', 'Efectivo'), ('tarjeta', 'Tarjeta'), ('transferencia', 'Transferencia')]
    TIPOS_ENTREGA =[('domicilio', 'Domicilio'), ('mostrador', 'Mostrador')]

    # Flujo del pedido (HU19): cada estado apunta al único estado que le sigue.
    # 'entregado' y 'cancelado' son finales: no tienen siguiente.
    TRANSICIONES = {
        'recibido': 'en_preparacion',
        'en_preparacion': 'listo',
        'listo': 'entregado',
        'entregado': None,
        'cancelado': None,
    }

    cliente = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='pedidos', on_delete=models.CASCADE) 
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='pedidos_creados', on_delete=models.CASCADE)
    sede = models.ForeignKey('menu.Sede', related_name='pedidos', on_delete=models.CASCADE)
    direccion = models.ForeignKey('users.Direccion', null=True, blank=True, on_delete=models.SET_NULL) 
    tipo_entrega = models.CharField(choices=TIPOS_ENTREGA, default='domicilio', max_length=20)
    metodo_pago = models.CharField(choices=METODOS_PAGO, max_length=20)
    observaciones = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2) 
    costo_domicilio = models.DecimalField(max_digits=12, decimal_places=2, default=0) 
    total = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(choices=ESTADOS, default='recibido', max_length=20)
    created_at = models.DateTimeField(auto_now_add=True) 
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
       return f'Pedido #{self.pk}'

    def siguiente_estado(self):
        return self.TRANSICIONES.get(self.estado)

    def puede_avanzar(self):
        return self.siguiente_estado() is not None

class DetallePedido(models.Model):
    pedido= models.ForeignKey(Pedido, related_name='detalles', on_delete=models.CASCADE)
    producto= models.ForeignKey('menu.Product', on_delete=models.PROTECT)
    cantidad= models.PositiveIntegerField()
    precio_unitario= models.DecimalField(max_digits=10, decimal_places=2)
    subtotal= models.DecimalField(max_digits=12, decimal_places=2)
    # Opciones elegidas al pedir (HU10), congeladas: [{'kind': 'size'|'addon'|'exclusion', 'name': ..., 'extra': '1500.00'}]
    opciones= models.JSONField(default=list, blank=True)

    @property
    def opciones_lista(self):
        """Las opciones listas para mostrar en las plantillas."""
        return [
            {**o, 'con_recargo': Decimal(o.get('extra') or '0') > 0}
            for o in self.opciones
        ]


class HistorialEstado(models.Model):
    """Momento en que un pedido entró a cada estado (HU43).

    Una fila por cada cambio de estado (y una al crear el pedido). Con ellas se mide
    cuánto tarda cada etapa, que es lo que necesitan HU32, HU34 y HU35.
    """
    pedido = models.ForeignKey(Pedido, related_name='historial_estados', on_delete=models.CASCADE)
    estado = models.CharField('estado', choices=Pedido.ESTADOS, max_length=20)
    entrada = models.DateTimeField('entrada al estado', default=timezone.now)

    class Meta:
        verbose_name = 'historial de estado'
        verbose_name_plural = 'historial de estados'
        ordering = ['entrada', 'id']

    def __str__(self):
        return f'Pedido #{self.pedido_id} · {self.get_estado_display()} · {self.entrada:%H:%M:%S}'

