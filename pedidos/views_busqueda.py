"""Búsqueda de pedidos y clientes con filtros para el administrador (HU33)."""
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils.dateparse import parse_date

from menu.models import Sede

from .models import Pedido
from .permissions import rol_requerido

User = get_user_model()
POR_PAGINA = 25
CAMPOS_PERSONA = ('first_name', 'last_name', 'username', 'email', 'phone')
# TODO HU24: cuando exista la zona de cobertura, agregar aquí el filtro por zona.


def _fecha(valor):
    """Una fecha AAAA-MM-DD válida o None (un valor inventado se ignora)."""
    try:
        return parse_date(valor)
    except ValueError:
        return None


def _texto(q, prefijo=''):
    filtro = Q()
    for campo in CAMPOS_PERSONA:
        filtro |= Q(**{f'{prefijo}{campo}__icontains': q})
    return filtro


def _paginar(request, consulta):
    pagina = Paginator(consulta, POR_PAGINA).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return pagina, params.urlencode()   # para conservar los filtros al paginar


@rol_requerido('admin')
def buscar_pedidos(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    if estado not in [valor for valor, _ in Pedido.ESTADOS]:
        estado = ''
    sede_txt = request.GET.get('sede', '')
    sede_id = int(sede_txt) if sede_txt.isdigit() and len(sede_txt) <= 9 else None
    desde = _fecha(request.GET.get('desde', ''))
    hasta = _fecha(request.GET.get('hasta', ''))

    pedidos = Pedido.objects.select_related('cliente', 'sede').order_by('-created_at', '-id')
    if q:
        filtro = _texto(q, 'cliente__')
        if q.isdigit() and len(q) <= 9:
            filtro |= Q(pk=int(q))          # también por número de pedido
        pedidos = pedidos.filter(filtro)
    if estado:
        pedidos = pedidos.filter(estado=estado)
    if sede_id:
        pedidos = pedidos.filter(sede_id=sede_id)
    if desde:
        pedidos = pedidos.filter(created_at__date__gte=desde)
    if hasta:
        pedidos = pedidos.filter(created_at__date__lte=hasta)

    pagina, qs = _paginar(request, pedidos)
    return render(request, 'pedidos/admin/buscar_pedidos.html', {
        'pagina': pagina, 'qs': qs, 'q': q, 'estado': estado, 'estados': Pedido.ESTADOS,
        'sede_sel': sede_id, 'sedes': Sede.objects.order_by('name'),
        'desde': desde.isoformat() if desde else '', 'hasta': hasta.isoformat() if hasta else '',
    })


@rol_requerido('admin')
def buscar_clientes(request):
    q = request.GET.get('q', '').strip()
    activo = request.GET.get('activo', '')
    if activo not in ('si', 'no'):
        activo = ''

    clientes = (
        User.objects.filter(role='cliente')
        .annotate(num_pedidos=Count('pedidos'))
        .order_by('first_name', 'username')
    )
    if q:
        clientes = clientes.filter(_texto(q))
    if activo:
        clientes = clientes.filter(is_active=(activo == 'si'))

    pagina, qs = _paginar(request, clientes)
    return render(request, 'pedidos/admin/buscar_clientes.html', {
        'pagina': pagina, 'qs': qs, 'q': q, 'activo': activo,
    })
