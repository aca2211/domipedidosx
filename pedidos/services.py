from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from menu.models import Feriado, SedeProduct, StockInsuficiente

from .estimacion import calcular_tiempo_estimado
from .capacidad import verificar_cupo
from .cart import Carrito, CarritoError
from .cobertura import verificar_cobertura
from .models import DetallePedido, HistorialEstado, Pedido
from .notificaciones import notificar_pedido
from django.contrib.auth import get_user_model


def _descontar_stock(sede, lineas):
    """HU29: descuenta las existencias de cada línea. Si alguna no alcanza, lanza CarritoError
    y la transacción que llama revierte todo (no queda pedido a medias)."""
    for linea in sorted(lineas, key=lambda l: l['producto'].id):
        sp = SedeProduct.objects.select_for_update().filter(sede=sede, product=linea['producto']).first()
        if sp is None:
            continue
        try:
            sp.descontar(linea['cantidad'])
        except StockInsuficiente:
            raise CarritoError(f'No hay existencias suficientes de «{linea["producto"].name}».')


def _devolver_stock(pedido):
    """HU29: al cancelar un pedido se devuelven sus unidades a la existencia de la sede."""
    for detalle in pedido.detalles.select_related('producto').order_by('producto_id'):
        sp = SedeProduct.objects.select_for_update().filter(sede=pedido.sede, product=detalle.producto).first()
        if sp is not None:
            sp.reponer(detalle.cantidad)


def _registrar_estado(pedido, estado):
    """HU43: guarda cuándo el pedido entró al estado indicado."""
    HistorialEstado.objects.create(pedido=pedido, estado=estado)


def tiempos_por_etapa(pedido):
    """HU43: duración de cada etapa del pedido, en minutos.

    Cada etapa dura desde que el pedido entró a ese estado hasta que entró al siguiente.
    La última etapa no tiene fin mientras el pedido siga abierto, así que no devuelve minutos.
    """
    entradas = list(pedido.historial_estados.order_by('entrada', 'id'))
    tiempos = []
    for actual, siguiente in zip(entradas, entradas[1:]):
        minutos = (siguiente.entrada - actual.entrada).total_seconds() / 60
        tiempos.append({
            'estado': actual.estado,
            'inicio': actual.entrada,
            'fin': siguiente.entrada,
            'minutos': round(minutos, 2),
        })
    return tiempos


def productos_bajo_minimo(sede):
    """HU30: productos de la sede con existencias en el mínimo o por debajo, los más críticos primero."""
    return (
        SedeProduct.objects
        .filter(sede=sede, stock__isnull=False, stock__lte=F('stock_minimo'))
        .select_related('product')
        .order_by('stock', 'product__name')
    )


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
        # select_for_update garantiza que dos pedidos simultáneos no superen el tope (HU26)
        from menu.models import Sede as _Sede
        sede = _Sede.objects.select_for_update().filter(pk=carrito.sede_id).first()
        if sede is None or not sede.is_active:
            raise CarritoError('La sede de tu carrito ya no está disponible.')
        feriado = Feriado.objects.filter(date=timezone.localdate()).first()
        if feriado:
            raise CarritoError(
                f'La sede {sede.name} no atiende hoy por ser feriado ({feriado.name}).'
            )
        if not sede.is_open_now():
            raise CarritoError(
                f'La sede {sede.name} está cerrada en este momento. '
                f'Atiende de {sede.opening_time:%H:%M} a {sede.closing_time:%H:%M}.'
            )
        resumen = carrito.resumen()
        if resumen['hay_faltantes']:
            raise CarritoError('Algún producto de tu carrito ya no existe. Revisa el carrito.')
        agotados = [l['producto'].name for l in resumen['lineas'] if not l['disponible']]
        if agotados:
            raise CarritoError('Ya no hay disponibilidad de: ' + ', '.join(agotados) + '.')
        if resumen['hay_opciones_invalidas']:
            raise CarritoError('Alguna opción de tu carrito ya no está disponible. Quita ese producto y vuelve a agregarlo.')
        # HU24 + HU25: la dirección debe tener cobertura y el subtotal alcanzar el mínimo de su zona
        costo_domicilio = Decimal('0')
        if tipo_entrega == 'domicilio':
            costo_domicilio = verificar_cobertura(sede, direccion, resumen['subtotal'])
        producto_ids = [l['producto'].pk for l in resumen['lineas']]
        verificar_cupo(sede, producto_ids)  # HU26 + HU27: rechaza si llena, sugiere alternativas

        tiempo_estimado = calcular_tiempo_estimado(
            sede,
            resumen['lineas'],
            tipo_entrega=tipo_entrega,
            direccion=direccion if tipo_entrega == 'domicilio' else None,
        )
        pedido = Pedido.objects.create(
            cliente=cliente,
            creado_por=creado_por or cliente,
            sede=sede,
            tipo_entrega=tipo_entrega,
            direccion=direccion if tipo_entrega == 'domicilio' else None,
            metodo_pago=metodo_pago,
            observaciones=observaciones,
            subtotal=resumen['subtotal'],
            costo_domicilio=costo_domicilio,
            total=resumen['subtotal'] + costo_domicilio,
            tiempo_estimado=tiempo_estimado,
            estado='recibido',
        )

        DetallePedido.objects.bulk_create([
            DetallePedido(
                pedido=pedido,
                producto=l['producto'],
                cantidad=l['cantidad'],
                precio_unitario=l['precio'],  # precio congelado (base + recargos de opciones)
                subtotal=l['subtotal'],
                # Copia de las opciones elegidas: no cambia si el menú se edita después (HU10)
                opciones=[
                    {'kind': o['kind'], 'name': o['name'], 'extra': str(o['extra'])}
                    for o in l['opciones']
                ],
            )
            for l in resumen['lineas']
        ])
        _descontar_stock(sede, resumen['lineas'])
        _registrar_estado(pedido, 'recibido')
        transaction.on_commit(lambda pk=pedido.pk: notificar_pedido(pk, 'confirmado'))
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
        _devolver_stock(pedido)
        _registrar_estado(pedido, 'cancelado')
        transaction.on_commit(lambda pk=pedido.pk: notificar_pedido(pk, 'cancelado'))
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
        if pedido.estado == 'listo' and pedido.tipo_entrega == 'domicilio':
            raise AvanceError(
                f'El pedido #{pedido.pk} es a domicilio; el operador debe asignarle un repartidor.'
            )
        if pedido.estado != estado_esperado:
            raise AvanceError(
                f'El pedido #{pedido.pk} ya cambió de estado. Revisa el tablero actualizado.'
            )
        pedido.estado = pedido.siguiente_estado()
        pedido.save(update_fields=['estado', 'updated_at'])
        _registrar_estado(pedido, pedido.estado)
        transaction.on_commit(lambda pk=pedido.pk: notificar_pedido(pk, 'estado'))
    return pedido


class AsignacionError(Exception):
    """No se pudo asignar el repartidor al pedido (HU22)."""


def asignar_repartidor(pedido_id, sede, repartidor_id):
    """El operador asigna un repartidor a un pedido listo a domicilio (HU22)."""
    User = get_user_model()
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id, sede=sede)
        if pedido.tipo_entrega != 'domicilio':
            raise AsignacionError('Solo los pedidos a domicilio requieren repartidor.')
        if pedido.estado != 'listo':
            raise AsignacionError(
                f'El pedido #{pedido.pk} debe estar en estado «Listo» para asignar repartidor.'
            )
        repartidor = User.objects.filter(pk=repartidor_id, role='repartidor', is_active=True).first()
        if repartidor is None:
            raise AsignacionError('Selecciona un repartidor activo válido.')
        if repartidor.sede_id and repartidor.sede_id != sede.id:
            raise AsignacionError('Ese repartidor pertenece a otra sede.')

        pedido.repartidor = repartidor
        pedido.estado = 'en_camino'
        pedido.save(update_fields=['repartidor', 'estado', 'updated_at'])
        _registrar_estado(pedido, 'en_camino')
        transaction.on_commit(lambda pk=pedido.pk: notificar_pedido(pk, 'asignado'))
        transaction.on_commit(lambda pk=pedido.pk: notificar_pedido(pk, 'estado'))
    return pedido


class EntregaError(Exception):
    """No se pudo registrar la entrega del pedido (HU23)."""


def registrar_entrega(pedido_id, repartidor):
    """El repartidor marca como entregado un pedido suyo en camino (HU23)."""
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id, repartidor=repartidor)
        if pedido.estado != 'en_camino':
            raise EntregaError(
                f'El pedido #{pedido.pk} no está en camino (estado actual: {pedido.get_estado_display().lower()}).'
            )
        pedido.estado = 'entregado'
        pedido.save(update_fields=['estado', 'updated_at'])
        _registrar_estado(pedido, 'entregado')
        transaction.on_commit(lambda pk=pedido.pk: notificar_pedido(pk, 'estado'))
    return pedido