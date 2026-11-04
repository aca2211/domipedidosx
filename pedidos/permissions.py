from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404

from menu.models import Sede

def rol_requerido(*roles):
    """Protege una vista por rol. Anónimo -> login; rol incorrecto -> 403."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:
                raise PermissionDenied
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador

def obtener_sede(request):
    
    sede = getattr(request.user, 'sede', None)
    if sede is not None:
        return sede
    sede_id = request.GET.get('sede') or request.POST.get('sede')
    if not sede_id:
        return None
    if not str(sede_id).isdigit():
        raise Http404
    return get_object_or_404(Sede, pk=sede_id, is_active=True)