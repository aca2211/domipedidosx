"""Panel del repartidor y registro de entrega (HU23)."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Pedido
from .permissions import rol_requerido
from .services import EntregaError, registrar_entrega


@rol_requerido('repartidor')
def panel_repartidor(request):
    """Lista los pedidos en camino asignados al repartidor y los entregados hoy (HU23)."""
    en_camino = (
        Pedido.objects
        .filter(repartidor=request.user, estado='en_camino')
        .select_related('cliente', 'sede', 'direccion')
        .prefetch_related('detalles__producto')
        .order_by('updated_at', 'id')
    )
    entregados_hoy = (
        Pedido.objects
        .filter(repartidor=request.user, estado='entregado', updated_at__date=timezone.localdate())
        .select_related('cliente', 'sede', 'direccion')
        .order_by('-updated_at', '-id')
    )
    return render(request, 'pedidos/repartidor/panel.html', {
        'en_camino': en_camino,
        'entregados_hoy': entregados_hoy,
    })


@rol_requerido('repartidor')
@require_POST
def marcar_entregado(request, pk):
    """Registra la entrega de un pedido asignado al repartidor (HU23)."""
    get_object_or_404(Pedido, pk=pk, repartidor=request.user)
    try:
        pedido = registrar_entrega(pk, request.user)
    except EntregaError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f'Pedido #{pedido.pk} marcado como entregado.')
    return redirect('repartidor_panel')