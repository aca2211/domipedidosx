"""Topes de capacidad de la cocina por sede y franja horaria (HU26, HU27).

HU26: `verificar_cupo` rechaza el pedido si la franja de la sede está llena.
HU27: al rechazar, el mensaje incluye otras sedes con cupo y la hora en que
      se libera la franja actual, para que el cliente pueda reorientar su pedido.
"""
from datetime import datetime

from django.utils import timezone

from menu.models import Sede, SedeProduct, TopeCapacidad
from .cart import CarritoError
from .models import Pedido


class CapacidadError(CarritoError):
    """La sede alcanzó su tope; el mensaje ya incluye las alternativas (HU26, HU27).

    Hereda de CarritoError para que las vistas existentes la capturen sin cambios.
    """


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

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


def _tiene_cupo(sede, momento):
    """True si la sede no tiene tope activo en ese momento o aún le quedan cupos."""
    tope = TopeCapacidad.vigente(sede, momento.time())
    if tope is None:
        return True
    return contar_pedidos_en_franja(tope, momento.date()) < tope.max_pedidos



# ---------------------------------------------------------------------------
# HU28: estado actual de ocupación de la cocina
# ---------------------------------------------------------------------------

class EstadoCapacidad:
    """Ocupación actual de la sede en su franja vigente (HU28)."""

    def __init__(self, tope, ocupados):
        self.tope = tope
        self.ocupados = ocupados

    @property
    def porcentaje(self):
        return round(self.ocupados * 100 / self.tope.max_pedidos)

    @property
    def cupos(self):
        return max(0, self.tope.max_pedidos - self.ocupados)

    @property
    def lleno(self):
        return self.ocupados >= self.tope.max_pedidos

    @property
    def cerca_del_limite(self):
        """True si llegó al umbral de alerta pero aún quedan cupos."""
        return (
            not self.lleno
            and self.ocupados * 100 >= self.tope.umbral_alerta * self.tope.max_pedidos
        )


def estado_capacidad(sede, momento=None):
    """EstadoCapacidad de la sede en su franja actual, o None si no hay tope."""
    momento = momento or timezone.localtime()
    tope = TopeCapacidad.vigente(sede, momento.time())
    if tope is None:
        return None
    return EstadoCapacidad(tope=tope, ocupados=contar_pedidos_en_franja(tope, momento.date()))


# ---------------------------------------------------------------------------
# HU27: buscar alternativas cuando la franja está llena
# ---------------------------------------------------------------------------

def buscar_alternativas(sede_llena, producto_ids, tope, momento):
    """Devuelve (sedes_con_cupo, reabre_a) para sugerirle opciones al cliente (HU27).

    sedes_con_cupo: otras sedes activas, abiertas, con cupo y que venden
                    todos los productos del carrito.
    reabre_a:       hora en que termina la franja llena, si la sede sigue
                    abierta en ese momento; None en caso contrario.
    """
    producto_ids = list(producto_ids)
    sedes_con_cupo = []

    for otra in Sede.objects.filter(is_active=True).exclude(pk=sede_llena.pk).order_by('name'):
        if not otra.is_open_now():
            continue
        if not _tiene_cupo(otra, momento):
            continue
        # La sede alternativa debe vender y tener disponibles todos los productos del carrito
        disponibles = SedeProduct.objects.filter(
            sede=otra, product_id__in=producto_ids, is_available=True,
        ).count()
        if disponibles == len(producto_ids):
            sedes_con_cupo.append(otra)

    # La franja termina a tope.hora_fin; solo se menciona si la sede sigue abierta a esa hora
    reabre_a = tope.hora_fin if sede_llena.is_open_at(tope.hora_fin) else None

    return sedes_con_cupo, reabre_a


def _mensaje_lleno(sede, tope, sedes_con_cupo, reabre_a):
    texto = (
        f'La sede {sede.name} alcanzó el tope de {tope.max_pedidos} pedidos '
        f'para la franja {tope.hora_inicio:%H:%M}–{tope.hora_fin:%H:%M}.'
    )
    if sedes_con_cupo:
        nombres = ', '.join(s.name for s in sedes_con_cupo)
        texto += f' Puedes pedir en otra sede con cupo: {nombres}.'
    if reabre_a:
        texto += f' O vuelve a intentarlo en esta sede a partir de las {reabre_a:%H:%M}.'
    if not sedes_con_cupo and not reabre_a:
        texto += ' Por ahora no hay otra sede disponible; intenta de nuevo más tarde.'
    return texto


# ---------------------------------------------------------------------------
# HU26 + HU27: punto de entrada desde services.py
# ---------------------------------------------------------------------------

def verificar_cupo(sede, producto_ids=(), momento=None):
    """Lanza CapacidadError si la sede llegó al tope en su franja actual (HU26).

    Si está llena, el mensaje incluye alternativas de sede y hora (HU27).
    Debe llamarse dentro de `transaction.atomic()` con la sede bloqueada
    via `select_for_update()` para evitar condiciones de carrera.
    """
    momento = momento or timezone.localtime()
    tope = TopeCapacidad.vigente(sede, momento.time())
    if tope is None:
        return                                      # sin tope → sin límite
    ocupados = contar_pedidos_en_franja(tope, momento.date())
    if ocupados >= tope.max_pedidos:
        sedes_con_cupo, reabre_a = buscar_alternativas(sede, producto_ids, tope, momento)
        raise CapacidadError(_mensaje_lleno(sede, tope, sedes_con_cupo, reabre_a))
