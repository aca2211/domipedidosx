"""Pedidos tomados por el operador en nombre de un cliente (HU15)."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from menu.models import Product, ProductOption, Sede, SedeProduct
from .services import productos_bajo_minimo

from .capacidad import estado_capacidad
from .cart import Carrito, CarritoError
from .cobertura import evaluar_direcciones
from .forms import PedidoOperadorForm
from .models import Pedido
from .permissions import rol_requerido
from .services import crear_pedido

User = get_user_model()

SEDE_KEY = 'operador_sede_id'
CLIENTE_KEY = 'operador_cliente_id'


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _opciones_del_post(post):
    """Ids de las opciones elegidas: un tamaño (radio «tamano») y varias adiciones/exclusiones («opciones»)."""
    crudos = [post.get('tamano')] + post.getlist('opciones')
    return [i for i in (_entero(v) for v in crudos if v) if i is not None]


def sede_del_operador(request):
    """Sede con la que trabaja el operador.

    Si el usuario tiene sede asignada (CustomUser.sede) esa es siempre su sede.
    Respaldo TEMPORAL para operadores sin sede: se elige con ?sede=ID y se recuerda en la sesión.
    """
    sede_propia_id = getattr(request.user, 'sede_id', None)
    if sede_propia_id:
        return Sede.objects.filter(pk=sede_propia_id, is_active=True).first()

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
        'alertas_stock': productos_bajo_minimo(sede),
        'capacidad': estado_capacidad(sede),  # HU28
    })


# ---------------------------------------------------------------------------
# HU15: armar y confirmar el pedido en nombre del cliente elegido
# ---------------------------------------------------------------------------

def _preparar(request):
    """Devuelve (sede, cliente, carrito, redireccion). Si falta sede o cliente, solo trae la redirección."""
    sede = sede_del_operador(request)
    cliente = cliente_elegido(request)
    if sede is None or cliente is None:
        messages.warning(request, 'Elige la sede y el cliente para tomar el pedido.')
        return None, None, None, redirect('operador_elegir_cliente')
    carrito = Carrito(request)
    if carrito.sede_id and carrito.sede_id != sede.id:
        carrito.vaciar()  # el carrito era de otra sede
    return sede, cliente, carrito, None


def _productos_de_la_sede(sede):
    disponibles = SedeProduct.objects.filter(sede=sede, is_available=True)
    productos = list(
        Product.objects.filter(pk__in=disponibles.values('product'))
        .select_related('category')
        .prefetch_related(Prefetch(
            'options', queryset=ProductOption.objects.filter(is_active=True), to_attr='opciones_activas',
        ))
        .order_by('category__name', 'name')
    )
    for p in productos:
        p.tamanos = [o for o in p.opciones_activas if o.kind == ProductOption.SIZE]
        p.adiciones = [o for o in p.opciones_activas if o.kind == ProductOption.ADDON]
        p.exclusiones = [o for o in p.opciones_activas if o.kind == ProductOption.EXCLUSION]
    return productos


def _render_armar(request, sede, cliente, carrito, form):
    # HU24: el domicilio se cobra según la zona de la dirección elegida (solo si la entrega es a domicilio)
    direcciones = list(cliente.direcciones.all())
    costos = evaluar_direcciones(sede, direcciones, carrito.resumen()['subtotal'])
    elegida = next((d for d in direcciones if str(d.pk) == str(form['direccion'].value())), None)
    if form['tipo_entrega'].value() == 'mostrador':
        elegida = None
    contexto = {
        'costos_direccion': costos,
        'aviso_cobertura': costos['direcciones'][str(elegida.pk)]['aviso'] if elegida else None,
        'sede': sede,
        'cliente': cliente,
        'productos': _productos_de_la_sede(sede),
        'carrito': carrito,
        'form': form,
        'tiene_direcciones': cliente.direcciones.exists(),
    }
    contexto.update(carrito.resumen(direccion=elegida))
    return render(request, 'pedidos/operador/armar.html', contexto)


@rol_requerido('operador')
def armar_pedido(request):
    sede, cliente, carrito, salida = _preparar(request)
    if salida:
        return salida
    return _render_armar(request, sede, cliente, carrito, PedidoOperadorForm(cliente=cliente))


@rol_requerido('operador')
@require_POST
def agregar_producto(request):
    sede, cliente, carrito, salida = _preparar(request)
    if salida:
        return salida
    try:
        carrito.agregar(
            _entero(request.POST.get('product_id')),
            sede.id,  # el operador siempre pide en su sede
            request.POST.get('cantidad', 1),
            _opciones_del_post(request.POST),
        )
    except CarritoError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, 'Producto agregado al pedido.')
    return redirect('operador_armar_pedido')


@rol_requerido('operador')
@require_POST
def actualizar_linea(request, clave):
    sede, cliente, carrito, salida = _preparar(request)
    if salida:
        return salida
    try:
        carrito.actualizar(clave, request.POST.get('cantidad'))
    except CarritoError as e:
        messages.error(request, str(e))
    return redirect('operador_armar_pedido')


@rol_requerido('operador')
@require_POST
def quitar_linea(request, clave):
    sede, cliente, carrito, salida = _preparar(request)
    if salida:
        return salida
    carrito.quitar(clave)
    messages.success(request, 'Producto quitado del pedido.')
    return redirect('operador_armar_pedido')


@rol_requerido('operador')
@require_POST
def confirmar_pedido_operador(request):
    sede, cliente, carrito, salida = _preparar(request)
    if salida:
        return salida
    form = PedidoOperadorForm(request.POST, cliente=cliente)
    if not form.is_valid():
        return _render_armar(request, sede, cliente, carrito, form)
    try:
        pedido = crear_pedido(
            carrito,
            cliente=cliente,
            metodo_pago=form.cleaned_data['metodo_pago'],
            direccion=form.cleaned_data['direccion'],
            observaciones=form.cleaned_data['observaciones'],
            creado_por=request.user,
            tipo_entrega=form.cleaned_data['tipo_entrega'],
        )
    except CarritoError as e:
        messages.error(request, str(e))
        return redirect('operador_armar_pedido')
    request.session.pop(CLIENTE_KEY, None)  # el siguiente pedido empieza eligiendo cliente
    messages.success(request, f'Pedido #{pedido.pk} creado a nombre de {cliente.get_full_name() or cliente.username}.')
    return redirect('operador_pedido_creado', pk=pedido.pk)


@rol_requerido('operador')
def pedido_creado_operador(request, pk):
    sede = sede_del_operador(request)
    pedido = get_object_or_404(
        Pedido.objects.select_related('cliente', 'sede', 'direccion').prefetch_related('detalles__producto'),
        pk=pk, sede=sede,
    )
    return render(request, 'pedidos/operador/pedido_creado.html', {'pedido': pedido})