from django.contrib import admin
from .models import Pedido, DetallePedido

class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 1

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id','cliente', 'creado_por', 'sede', 'tipo_entrega', 'metodo_pago', 'estado')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('estado', 'creado_por', 'sede')
    inlines = [DetallePedidoInline]