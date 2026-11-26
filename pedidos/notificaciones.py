"""Correos al cliente cuando su pedido se confirma, cambia de estado o se cancela (HU31).

El envío se dispara con transaction.on_commit desde services.py, así que solo sale
si el cambio quedó guardado. Un fallo del correo se registra en el log y no
interrumpe el flujo del pedido.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import Pedido

logger = logging.getLogger(__name__)


def _asunto_y_texto(pedido, evento):
    nombre = pedido.cliente.get_full_name() or pedido.cliente.username
    if evento == 'confirmado':
        asunto = f'Pedido #{pedido.pk} confirmado'
        texto = (
            f'Hola {nombre}, recibimos tu pedido #{pedido.pk} en la sede {pedido.sede.name}.\n'
            f'Total: ${pedido.total:,.0f}.\n'
        )
        if pedido.tiempo_estimado:
            texto += f'Tiempo estimado de entrega: {pedido.tiempo_estimado} minutos.\n'
    elif evento == 'cancelado':
        asunto = f'Pedido #{pedido.pk} cancelado'
        texto = f'Hola {nombre}, tu pedido #{pedido.pk} fue cancelado.\n'
    elif evento == 'asignado' and pedido.repartidor:
        rep_nombre = pedido.repartidor.get_full_name() or pedido.repartidor.username
        dir_texto = pedido.direccion.address if pedido.direccion else 'Sin dirección'
        asunto = f'Nuevo pedido asignado: #{pedido.pk}'
        texto = (
            f'Hola {rep_nombre}, se te asignó el pedido #{pedido.pk} de la sede {pedido.sede.name}.\n'
            f'Cliente: {nombre}\n'
            f'Dirección: {dir_texto}\n'
            f'Total a cobrar ({pedido.get_metodo_pago_display()}): ${pedido.total:,.0f}.\n'
        )
    elif pedido.estado == 'en_camino':
        rep_nombre = (
            (pedido.repartidor.get_full_name() or pedido.repartidor.username)
            if pedido.repartidor else 'un repartidor'
        )
        asunto = f'Tu pedido #{pedido.pk} va en camino'
        texto = f'Hola {nombre}, tu pedido #{pedido.pk} salió en camino con {rep_nombre}.\n'
    else:
        estado = pedido.get_estado_display().lower()
        asunto = f'Pedido #{pedido.pk}: {estado}'
        texto = f'Hola {nombre}, tu pedido #{pedido.pk} ahora está: {estado}.\n'
    return asunto, texto + '\nDomiPedidosX'


def notificar_pedido(pedido_id, evento):
    """Envía el correo del evento ('confirmado', 'estado', 'asignado' o 'cancelado')."""
    pedido = (
        Pedido.objects
        .select_related('cliente', 'repartidor', 'sede', 'direccion')
        .filter(pk=pedido_id)
        .first()
    )
    if pedido is None:
        return

    destinatario = (
        (pedido.repartidor.email if pedido.repartidor else '')
        if evento == 'asignado'
        else pedido.cliente.email
    )
    if not destinatario:
        return

    asunto, texto = _asunto_y_texto(pedido, evento)
    try:
        send_mail(asunto, texto, settings.DEFAULT_FROM_EMAIL, [destinatario])
    except Exception:
        logger.exception('No se pudo enviar el correo del pedido #%s (%s)', pedido_id, evento)