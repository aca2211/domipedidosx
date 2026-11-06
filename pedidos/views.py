from django.contrib import messages
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .cart import Carrito, CarritoError
from .forms import ConfirmarPedidoForm
from .models import Pedido
from .permissions import rol_requerido
from .services import CancelacionError, cancelar_pedido, crear_pedido


URL_CREAR_DIRECCION = 'direccion_crear'

# HU20: pasos que ve el cliente en el indicador de progreso
PASOS = ['recibido', 'en_preparacion', 'listo', 'entregado']
ESTADOS_FINALES = ('entregado', 'cancelado')


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _destino_seguro(request, defecto):
    destino = request.POST.get('next', '')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return destino
    return defecto


def _url_crear_direccion():
    try:
        return reverse(URL_CREAR_DIRECCION)
    except NoReverseMatch:
        return reverse('home')  



@rol_requerido('cliente')
def ver_carrito(request):
    carrito = Carrito(request)
    contexto = {'carrito': carrito, 'sede': carrito.sede}
    contexto.update(carrito.resumen())
    return render(request, 'pedidos/carrito.html', contexto)


@rol_requerido('cliente')
@require_POST
def agregar_al_carrito(request):
    carrito = Carrito(request)
    destino = _destino_seguro(request, reverse('carrito_ver'))
    try:
        cambio_sede = carrito.agregar(
            _entero(request.POST.get('product_id')),
            _entero(request.POST.get('sede_id')),
            request.POST.get('cantidad', 1),
        )
    except CarritoError as e:
        messages.error(request, str(e))
        return redirect(destino)
    if cambio_sede:
        messages.info(request, 'Cambiaste de sede, así que tu carrito anterior se vació.')
    messages.success(request, 'Producto agregado al carrito.')
    return redirect(destino)


@rol_requerido('cliente')
@require_POST
def actualizar_carrito(request, producto_id):
    try:
        Carrito(request).actualizar(producto_id, request.POST.get('cantidad'))
    except CarritoError as e:
        messages.error(request, str(e))
    return redirect('carrito_ver')


@rol_requerido('cliente')
@require_POST
def quitar_del_carrito(request, producto_id):
    Carrito(request).quitar(producto_id)
    messages.success(request, 'Producto quitado del carrito.')
    return redirect('carrito_ver')




@rol_requerido('cliente')
def confirmar_pedido(request):
    carrito = Carrito(request)
    if carrito.vacio:
        messages.warning(request, 'Tu carrito está vacío. Agrega productos para hacer un pedido.')
        return redirect('menu_list')
    if not request.user.direcciones.exists():
        messages.warning(request, 'Primero guarda una dirección de entrega para poder confirmar tu pedido.')
        return redirect(_url_crear_direccion())

    if request.method == 'POST':
        form = ConfirmarPedidoForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                pedido = crear_pedido(
                    carrito, cliente=request.user,
                    metodo_pago=form.cleaned_data['metodo_pago'],
                    direccion=form.cleaned_data['direccion'],
                    observaciones=form.cleaned_data['observaciones'],
                )
            except CarritoError as e:
                messages.error(request, str(e))
                return redirect('carrito_ver')
            messages.success(request, f'¡Pedido #{pedido.pk} recibido!')
            return redirect('pedido_creado', pk=pedido.pk)
    else:
        form = ConfirmarPedidoForm(user=request.user)

    contexto = {'form': form, 'carrito': carrito, 'sede': carrito.sede}
    contexto.update(carrito.resumen())
    return render(request, 'pedidos/confirmar.html', contexto)


@rol_requerido('cliente')
def pedido_creado(request, pk):
    pedido = get_object_or_404(
        Pedido.objects.select_related('sede', 'direccion').prefetch_related('detalles__producto'),
        pk=pk, cliente=request.user,
    )
    nombres = dict(Pedido.ESTADOS)
    indice = PASOS.index(pedido.estado) if pedido.estado in PASOS else -1
    pasos = [
        {'nombre': nombres[clave], 'hecho': i < indice, 'actual': i == indice}
        for i, clave in enumerate(PASOS)
    ]
    return render(request, 'pedidos/pedido_creado.html', {
        'pedido': pedido,
        'pasos': pasos,
        'refrescar': pedido.estado not in ESTADOS_FINALES,  # refresco automático mientras siga en curso
    })


@rol_requerido('cliente')
@require_POST
def cancelar_mi_pedido(request, pk):
    try:
        cancelar_pedido(pk, request.user)
    except Pedido.DoesNotExist:
        raise Http404  
    except CancelacionError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f'Tu pedido #{pk} fue cancelado.')
    return redirect('pedido_creado', pk=pk)


@rol_requerido('cliente')
def mis_pedidos(request):
    pedidos = (
        Pedido.objects.filter(cliente=request.user)
        .select_related('sede')
        .annotate(num_productos=Count('detalles'))
        .order_by('-created_at', '-id')
    )
    return render(request, 'pedidos/mis_pedidos.html', {'pedidos': pedidos})