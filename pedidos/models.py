from django.db import models
from django.conf import settings

class Pedido(models.Model):
    ESTADOS =[('recibido', 'Recibido'), ('en_preparacion', 'En preparacion'), ('listo', 'Listo'), ('entregado', 'Entregado'), ('cancelado', 'Cancelado')]
    METODOS_PAGO =[('efectivo', 'Efectivo'), ('tarjeta', 'Tarjeta'), ('transferencia', 'Transferencia')]
    TIPOS_ENTREGA =[('domicilio', 'Domicilio'), ('mostrador', 'Mostrador')]

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

class DetallePedido(models.Model):
    pedido= models.ForeignKey(Pedido, related_name='detalles', on_delete=models.CASCADE)
    producto= models.ForeignKey('menu.Product', on_delete=models.PROTECT)
    cantidad= models.PositiveIntegerField()
    precio_unitario= models.DecimalField(max_digits=10, decimal_places=2)
    subtotal= models.DecimalField(max_digits=12, decimal_places=2)
