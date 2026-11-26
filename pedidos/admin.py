from django.contrib import admin

from .models import DetallePedido, HistorialEstado, Pedido
from .services import tiempos_por_etapa


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0


class HistorialEstadoInline(admin.TabularInline):
    """HU43: historial de estados del pedido, solo lectura."""
    model = HistorialEstado
    extra = 0
    can_delete = False
    fields = ('estado', 'entrada')
    readonly_fields = ('estado', 'entrada')

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'sede', 'estado', 'total', 'created_at')
    list_filter = ('estado', 'sede')
    inlines = [DetallePedidoInline, HistorialEstadoInline]
    readonly_fields = ('tiempos_etapas',)

    def get_fields(self, request, obj=None):
        campos = super().get_fields(request, obj)
        return campos + ['tiempos_etapas'] if obj else campos

    @admin.display(description='Tiempo por etapa (HU43)')
    def tiempos_etapas(self, obj):
        tiempos = tiempos_por_etapa(obj)
        if not tiempos:
            return 'Aún no hay etapas terminadas.'
        return ' · '.join(
            f"{t['estado'].replace('_', ' ').capitalize()}: {t['minutos']:.1f} min"
            for t in tiempos
        )
