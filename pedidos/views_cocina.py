"""Tablero de cocina (HU18) y cambio de estado de los pedidos (HU19)."""
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from menu.models import Sede

from .models import Pedido
from .permissions import rol_requerido
from .services import AvanceError, avanzar_pedido
# TEMPORAL: la sede se elige con ?sede=ID y se recuerda en la sesión. Cuando exista
# CustomUser.sede, se cambia solo `sede_del_operador` y la cocina lo hereda.
from .views_operador import sede_del_operador

# Columnas del tablero: (estado guardado, título, texto del botón)
COLUMNAS = [
    ('recibido', 'Recibido', 'Empezar a preparar'),
    ('en_preparacion', 'En preparación', 'Marcar listo'),
    ('listo', 'Listo', 'Marcar entregado'),
]


@rol_requerido('cocina')
def tablero_cocina(request):
    sede = sede_del_operador(request)
    if sede is None:
        return render(request, 'pedidos/cocina/tablero.html', {
            'sede': None,
            'sedes': Sede.objects.filter(is_active=True).order_by('name'),
        })

    pedidos = (
        Pedido.objects
        .filter(sede=sede, estado__in=[c[0] for c in COLUMNAS])
        .select_related('cliente')
        .prefetch_related('detalles__producto')   # evita una consulta por tarjeta
        .order_by('created_at', 'id')             # el más antiguo primero
    )
    columnas = [
        {'estado': estado, 'titulo': titulo, 'accion': accion, 'pedidos': []}
        for estado, titulo, accion in COLUMNAS
    ]
    por_estado = {c['estado']: c for c in columnas}
    for pedido in pedidos:
        por_estado[pedido.estado]['pedidos'].append(pedido)

    return render(request, 'pedidos/cocina/tablero.html', {
        'sede': sede, 'sedes': [], 'columnas': columnas,
    })


@rol_requerido('cocina')
@require_POST
def avanzar_estado(request, pk):
    sede = sede_del_operador(request)
    if sede is None:
        messages.error(request, 'Primero elige la sede con la que vas a trabajar.')
        return redirect('cocina_tablero')
    try:
        pedido = avanzar_pedido(pk, sede, request.POST.get('estado_actual'))
    except Pedido.DoesNotExist:
        raise Http404  # no existe o es de otra sede
    except AvanceError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f'Pedido #{pedido.pk} ahora está {pedido.get_estado_display().lower()}.')
    return redirect('cocina_tablero')
