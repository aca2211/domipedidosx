from django.contrib import admin

from .models import DetallePedido, Pedido


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'sede', 'estado', 'total', 'created_at')
    list_filter = ('estado', 'sede')
    inlines = [DetallePedidoInline]

# Register your models here.
