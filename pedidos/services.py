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