"""Repetir un pedido anterior: vuelve a cargar sus productos en el carrito (HU17)."""
from menu.models import ProductOption

from .cart import CarritoError


def _ids_de_opciones(detalle):
    """Busca las opciones guardadas en el detalle entre las opciones activas actuales del producto.

    El detalle guarda las opciones por nombre (copia congelada), así que se vuelven a buscar por
    producto, tipo y nombre. Devuelve (ids encontrados, nombres que ya no existen).
    """
    ids, faltantes = [], []
    for o in detalle.opciones:
        opcion = ProductOption.objects.filter(
            product=detalle.producto, kind=o.get('kind'), name=o.get('name'), is_active=True,
        ).first()
        if opcion is None:
            faltantes.append(str(o.get('name')))
        else:
            ids.append(opcion.id)
    return ids, faltantes


def repetir_pedido(pedido, carrito):
    """Carga los productos de `pedido` en el carrito. Devuelve (agregados, omitidos).

    - Parte de un carrito vacío; si ninguna línea entra, deja el carrito como estaba.
    - Usa precios y disponibilidad actuales, no los del pedido viejo.
    - Una línea cuyas opciones ya no existen se omite entera (no se cambia el pedido en silencio).
    - `omitidos` es una lista de textos aptos para mostrar al usuario.
    """
    sede_previa, items_previos = carrito.sede_id, dict(carrito.items)
    carrito.vaciar()
    agregados, omitidos = 0, []
    for d in pedido.detalles.select_related('producto'):
        nombre = d.producto.name
        ids, faltantes = _ids_de_opciones(d)
        if faltantes:
            omitidos.append(f'{nombre} (ya no está disponible: {", ".join(faltantes)})')
            continue
        try:
            carrito.agregar(d.producto_id, pedido.sede_id, d.cantidad, ids)
        except CarritoError as e:
            omitidos.append(f'{nombre} ({e})')
        else:
            agregados += 1
    if not agregados and items_previos:
        carrito.sede_id, carrito.items = sede_previa, items_previos
        carrito._guardar()
    return agregados, omitidos
