"""Repetir un pedido del historial (HU17)."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .cart import Carrito
from .models import Pedido
from .permissions import rol_requerido
from .repetir import repetir_pedido


@rol_requerido('cliente')
@require_POST
def repetir_mi_pedido(request, pk):
    pedido = get_object_or_404(
        Pedido.objects.prefetch_related('detalles__producto'),
        pk=pk, cliente=request.user,   # solo pedidos propios
    )
    carrito = Carrito(request)
    tenia_carrito = not carrito.vacio
    agregados, omitidos = repetir_pedido(pedido, carrito)

    if not agregados:
        messages.error(
            request,
            f'No pudimos repetir el pedido #{pedido.pk}: ' + '; '.join(omitidos) + '.',
        )
        return redirect('mis_pedidos')

    messages.success(
        request,
        f'Agregamos al carrito los productos del pedido #{pedido.pk}. '
        'Revisa los precios y confirma cuando quieras.',
    )
    if omitidos:
        messages.warning(request, 'No se pudieron agregar: ' + '; '.join(omitidos) + '.')
    if tenia_carrito:
        messages.info(request, 'Tu carrito anterior se reemplazó.')
    return redirect('carrito_ver')
