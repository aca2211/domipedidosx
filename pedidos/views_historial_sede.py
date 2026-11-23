"""Historial de pedidos de la sede del operador (HU44)."""
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from .models import Pedido
from .permissions import rol_requerido
from .views_operador import sede_del_operador

POR_PAGINA = 25


@rol_requerido('operador')
def historial_sede(request):
    sede = sede_del_operador(request)
    if sede is None:
        # Sin sede se vuelve al panel, que muestra el selector (temporal, igual que HU21)
        return redirect('operador_panel')

    estado = request.GET.get('estado', '')
    if estado not in [valor for valor, _ in Pedido.ESTADOS]:
        estado = ''  # un estado inventado se ignora y se muestran todos

    pedidos = (
        Pedido.objects
        .filter(sede=sede)
        .select_related('cliente')            # evita una consulta por fila
        .order_by('-created_at', '-id')       # el más reciente primero
    )
    if estado:
        pedidos = pedidos.filter(estado=estado)

    pagina = Paginator(pedidos, POR_PAGINA).get_page(request.GET.get('page'))
    return render(request, 'pedidos/operador/historial.html', {
        'sede': sede, 'pagina': pagina, 'estado': estado, 'estados': Pedido.ESTADOS,
    })
