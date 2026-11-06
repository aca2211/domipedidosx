"""Pedidos tomados por el operador en nombre de un cliente (HU15)."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from menu.models import Sede

from .cart import Carrito
from .models import Pedido
from .permissions import rol_requerido

User = get_user_model()

SEDE_KEY = 'operador_sede_id'
CLIENTE_KEY = 'operador_cliente_id'


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def sede_del_operador(request):
    """Sede con la que trabaja el operador.

    TEMPORAL: se elige con ?sede=ID y se recuerda en la sesión.
    Cuando el backend agregue CustomUser.sede, solo hay que cambiar esta función
    para que devuelva request.user.sede.
    """
    if 'cambiar_sede' in request.GET:
        request.session.pop(SEDE_KEY, None)
    sede_id = _entero(request.GET.get('sede')) or request.session.get(SEDE_KEY)
    sede = Sede.objects.filter(pk=sede_id, is_active=True).first() if sede_id else None
    if sede:
        request.session[SEDE_KEY] = sede.id
    else:
        request.session.pop(SEDE_KEY, None)
    return sede


def cliente_elegido(request):
    cliente_id = request.session.get(CLIENTE_KEY)
    if not cliente_id:
        return None
    return User.objects.filter(pk=cliente_id, role='cliente', is_active=True).first()


@rol_requerido('operador')
def elegir_cliente(request):
    sede = sede_del_operador(request)
    q = request.GET.get('q', '').strip()
    resultados = []
    if sede and q:
        resultados = list(
            User.objects.filter(role='cliente', is_active=True)
            .filter(Q(username__icontains=q) | Q(phone__icontains=q))
            .order_by('username')[:10]
        )
    return render(request, 'pedidos/operador/elegir_cliente.html', {
        'sede': sede,
        'sedes': Sede.objects.filter(is_active=True).order_by('name') if sede is None else [],
        'q': q,
        'resultados': resultados,
        'cliente': cliente_elegido(request),
    })


@rol_requerido('operador')
@require_POST
def seleccionar_cliente(request):
    if sede_del_operador(request) is None:
        messages.error(request, 'Primero elige la sede con la que vas a trabajar.')
        return redirect('operador_elegir_cliente')
    cliente = get_object_or_404(
        User, pk=_entero(request.POST.get('cliente_id')), role='cliente', is_active=True,
    )
    Carrito(request).vaciar()  # un pedido nuevo siempre parte de un carrito limpio
    request.session[CLIENTE_KEY] = cliente.id
    messages.success(request, f'Cliente seleccionado: {cliente.get_full_name() or cliente.username}.')
    return redirect('operador_elegir_cliente')


@rol_requerido('operador')
def panel_operador(request):
    """Panel del operador (HU21): pedidos del día de su sede + enlaces a los módulos."""
    sede = sede_del_operador(request)
    if sede is None:
        # Sin sede se muestra el selector (temporal, igual que en HU15)
        return render(request, 'pedidos/operador/panel.html', {
            'sede': None,
            'sedes': Sede.objects.filter(is_active=True).order_by('name'),
        })

    pedidos = (
        Pedido.objects
        .filter(sede=sede, created_at__date=timezone.localdate())  # "hoy" en America/Bogota
        .select_related('cliente')                                  # evita una consulta por fila
        .order_by('-created_at', '-id')                             # el más reciente primero
    )
    return render(request, 'pedidos/operador/panel.html', {
        'sede': sede,
        'sedes': [],
        'pedidos': pedidos,
    })
