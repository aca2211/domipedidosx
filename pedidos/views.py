from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .cart import Carrito, CarritoError
from .permissions import rol_requerido

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


# ---------- HU13 · Carrito ----------

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

# Create your views here.
