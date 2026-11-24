"""Verificación de topes de capacidad de la cocina por sede y franja horaria (HU26).

`verificar_cupo` se llama dentro de la transacción atómica de `crear_pedido`,
con la fila de la sede bloqueada con SELECT FOR UPDATE, para que dos peticiones
concurrentes no puedan superar el tope al mismo tiempo.
"""
from datetime import datetime

from django.utils import timezone

from menu.models import TopeCapacidad
from .cart import CarritoError
from .models import Pedido


class CapacidadError(CarritoError):
    """La sede alcanzó su tope de pedidos en la franja actual (HU26).

    Hereda de CarritoError para que las vistas existentes la capturen sin cambios.
    """


def contar_pedidos_en_franja(tope, fecha):
    """Pedidos no cancelados de la sede creados dentro de la franja ese día."""
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(fecha, tope.hora_inicio), tz)
    fin    = timezone.make_aware(datetime.combine(fecha, tope.hora_fin),    tz)
    return (
        Pedido.objects
        .filter(sede_id=tope.sede_id, created_at__gte=inicio, created_at__lt=fin)
        .exclude(estado='cancelado')
        .count()
    )


def verificar_cupo(sede, momento=None):
    """Lanza CapacidadError si la sede llegó al tope en su franja actual (HU26).

    Debe llamarse dentro de un bloque `transaction.atomic()`, con la sede
    bloqueada via `select_for_update()`, para garantizar atomicidad.
    """
    momento = momento or timezone.localtime()
    tope = TopeCapacidad.vigente(sede, momento.time())
    if tope is None:
        return                      # sin tope configurado → sin límite
    ocupados = contar_pedidos_en_franja(tope, momento.date())
    if ocupados >= tope.max_pedidos:
        raise CapacidadError(
            f'La sede {sede.name} alcanzó el tope de {tope.max_pedidos} pedidos '            f'para la franja {tope.hora_inicio:%H:%M}–{tope.hora_fin:%H:%M}. '            f'Intenta de nuevo cuando termine la franja o elige otra sede.'
        )
