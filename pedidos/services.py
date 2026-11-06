from django.db import transaction

from .cart import Carrito, CarritoError
from .models import DetallePedido, Pedido


def crear_pedido(carrito: Carrito, cliente, metodo_pago, direccion=None,
                 observaciones='', creado_por=None, tipo_entrega='domicilio'):
    """Convierte el carrito en un Pedido (HU14). Reutilizable por el operador (HU15).

    Vuelve a validar disponibilidad y congela el precio unitario.
    Lanza CarritoError si algo impide crear el pedido.
    """
    if carrito.vacio:
        raise CarritoError('Tu carrito está vacío.')
    if tipo_entrega == 'domicilio' and direccion is None:
        raise CarritoError('Elige una dirección de entrega.')

    with transaction.atomic():
        sede = carrito.sede
        if sede is None or not sede.is_active:
            raise CarritoError('La sede de tu carrito ya no está disponible.')
        resumen = carrito.resumen()
        if resumen['hay_faltantes']:
            raise CarritoError('Algún producto de tu carrito ya no existe. Revisa el carrito.')
        agotados = [l['producto'].name for l in resumen['lineas'] if not l['disponible']]
        if agotados:
            raise CarritoError('Ya no hay disponibilidad de: ' + ', '.join(agotados) + '.')

        pedido = Pedido.objects.create(
            cliente=cliente,
            creado_por=creado_por or cliente,
            sede=sede,
            tipo_entrega=tipo_entrega,
            direccion=direccion if tipo_entrega == 'domicilio' else None,
            metodo_pago=metodo_pago,
            observaciones=observaciones,
            subtotal=resumen['subtotal'],
            costo_domicilio=resumen['costo_domicilio'],
            total=resumen['total'],
            estado='recibido',
        )
        DetallePedido.objects.bulk_create([
            DetallePedido(
                pedido=pedido,
                producto=l['producto'],
                cantidad=l['cantidad'],
                precio_unitario=l['precio'],  # precio congelado
                subtotal=l['subtotal'],
            )
            for l in resumen['lineas']
        ])
    carrito.vaciar()
    return pedido




class CancelacionError(Exception):
    """El pedido no se puede cancelar; el mensaje es apto para el usuario (HU16)."""


MENSAJES_NO_CANCELABLE = {
    'en_preparacion': 'Tu pedido ya está en preparación y no se puede cancelar.',
    'listo': 'Tu pedido ya está listo y no se puede cancelar.',
    'entregado': 'Tu pedido ya fue entregado y no se puede cancelar.',
    'cancelado': 'Este pedido ya estaba cancelado.',
}


def cancelar_pedido(pedido_id, cliente):
    """El cliente cancela su propio pedido, solo mientras esté en «recibido» (HU16).

    Lanza Pedido.DoesNotExist si el pedido no existe o es de otro cliente, y
    CancelacionError si ya no está en «recibido». El pedido no se borra: pasa a «cancelado».
    """
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id, cliente=cliente)
        if pedido.estado != 'recibido':
            raise CancelacionError(
                MENSAJES_NO_CANCELABLE.get(pedido.estado, 'Este pedido ya no se puede cancelar.')
            )
        pedido.estado = 'cancelado'
        pedido.save(update_fields=['estado', 'updated_at'])
    return pedido


class AvanceError(Exception):
    """El pedido no se puede avanzar; el mensaje es apto para el usuario (HU19)."""


def avanzar_pedido(pedido_id, sede, estado_esperado):
    """La cocina avanza un pedido de su sede al siguiente estado (HU19).

    - Lanza Pedido.DoesNotExist si el pedido no existe o es de otra sede.
    - Lanza AvanceError si el pedido ya es final (entregado/cancelado) o si ya
      cambió de estado desde que el tablero lo mostró (`estado_esperado`),
      para no saltarse pasos.
    """
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id, sede=sede)
        if not pedido.puede_avanzar():
            raise AvanceError(
                f'El pedido #{pedido.pk} está {pedido.get_estado_display().lower()} y no se puede modificar.'
            )
        if pedido.estado != estado_esperado:
            raise AvanceError(
                f'El pedido #{pedido.pk} ya cambió de estado. Revisa el tablero actualizado.'
            )
        pedido.estado = pedido.siguiente_estado()
        pedido.save(update_fields=['estado', 'updated_at'])
    return pedido
