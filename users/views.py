from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django.db.models import Case, IntegerField, Q, Value, When

from menu.models import Product

from .forms import DireccionForm, PerfilForm, RegistroForm
from .models import Direccion


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'¡Bienvenido, {user.first_name}! Tu cuenta fue creada.')
            return redirect('home')
    else:
        form = RegistroForm()
    return render(request, 'registration/register.html', {'form': form})


def home(request):
    if request.user.is_authenticated:
        return render(request, 'home.html')

    destacados = (
        Product.objects.filter(
            sede_products__is_available=True,
            sede_products__sede__is_active=True,
        )
        .annotate(
            tiene_foto=Case(
                When(Q(image='') & Q(image_url=''), then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
        )
        .distinct()
        .order_by('-tiene_foto', 'name', 'pk')[:3]
    )
    return render(request, 'inicio_publico.html', {'destacados': destacados})


# ---------- Perfil y direcciones del cliente (HU05) ----------

def solo_clientes(vista):
    """Exige sesión iniciada y rol cliente; los demás roles vuelven al panel."""
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if request.user.role != 'cliente':
            messages.warning(request, 'Esta sección es solo para clientes.')
            return redirect('home')
        return vista(request, *args, **kwargs)
    return envoltura


def _next(request):
    return request.POST.get('next') or request.GET.get('next') or ''


def _destino_seguro(request, defecto):
    destino = _next(request)
    if destino and url_has_allowed_host_and_scheme(
            destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return destino
    return defecto


@solo_clientes
def perfil(request):
    if request.method == 'POST':
        form = PerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu perfil fue actualizado.')
            return redirect('perfil')
    else:
        form = PerfilForm(instance=request.user)
    return render(request, 'users/perfil.html', {
        'form': form, 'direcciones': request.user.direcciones.all(),
    })


@solo_clientes
def direccion_lista(request):
    return render(request, 'users/direccion_lista.html', {
        'direcciones': request.user.direcciones.all(),
    })


@solo_clientes
def direccion_crear(request):
    if request.method == 'POST':
        form = DireccionForm(request.POST)
        if form.is_valid():
            direccion = form.save(commit=False)
            direccion.user = request.user
            if not request.user.direcciones.exists():
                direccion.is_default = True   # la primera siempre es la principal
            direccion.save()
            messages.success(request, 'Dirección guardada.')
            return redirect(_destino_seguro(request, 'direccion_lista'))
    else:
        form = DireccionForm()
    return render(request, 'users/direccion_form.html', {
        'form': form, 'titulo': 'Nueva dirección', 'next': _next(request),
    })


@solo_clientes
def direccion_editar(request, pk):
    direccion = get_object_or_404(Direccion, pk=pk, user=request.user)
    if request.method == 'POST':
        form = DireccionForm(request.POST, instance=direccion)
        if form.is_valid():
            direccion = form.save(commit=False)
            # siempre debe quedar una principal
            hay_otra = request.user.direcciones.filter(is_default=True).exclude(pk=direccion.pk).exists()
            if not direccion.is_default and not hay_otra:
                direccion.is_default = True
            direccion.save()
            messages.success(request, 'Dirección actualizada.')
            return redirect(_destino_seguro(request, 'direccion_lista'))
    else:
        form = DireccionForm(instance=direccion)
    return render(request, 'users/direccion_form.html', {
        'form': form, 'titulo': 'Editar dirección', 'next': _next(request),
    })


@solo_clientes
@require_POST
def direccion_eliminar(request, pk):
    direccion = get_object_or_404(Direccion, pk=pk, user=request.user)
    era_principal = direccion.is_default
    direccion.delete()
    if era_principal:
        otra = request.user.direcciones.first()
        if otra:
            otra.is_default = True
            otra.save()
    messages.success(request, 'Dirección eliminada.')
    return redirect('direccion_lista')


@solo_clientes
@require_POST
def direccion_principal(request, pk):
    direccion = get_object_or_404(Direccion, pk=pk, user=request.user)
    direccion.is_default = True
    direccion.save()
    messages.success(request, f'«{direccion.label}» es ahora tu dirección principal.')
    return redirect('direccion_lista')


def manual_usuario(request):
    from django.conf import settings
    from django.utils.safestring import mark_safe
    from markdown import markdown
    from markdown.extensions.toc import TocExtension, slugify_unicode

    archivo = settings.BASE_DIR / 'docs' / 'manual_de_usuario.md'
    contenido = archivo.read_text(encoding='utf-8')

    # El Markdown viene de un archivo versionado del proyecto.
    html = markdown(
        contenido,
        extensions=['tables', TocExtension(slugify=slugify_unicode)],
    )
    return render(request, 'manual_usuario.html', {'manual_html': mark_safe(html)})
