from .cart import SESSION_KEY


def carrito(request):
    """Cantidad de productos en el carrito para el menú de navegación (sin consultas a BD)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated or user.role != 'cliente':
        return {}
    data = request.session.get(SESSION_KEY) or {}
    return {'carrito_cantidad': sum((data.get('items') or {}).values())}