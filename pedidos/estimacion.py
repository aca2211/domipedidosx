"""Cálculo del tiempo estimado de entrega (HU32)."""
from menu.models import ZonaCobertura
from .capacidad import estado_capacidad

TIEMPO_BASE_PREPARACION = 15
TIEMPO_BASE_DOMICILIO = 20


def _minutos_zona(zona):
    """Obtiene los minutos configurados en ZonaCobertura sin depender del nombre exacto del campo."""
    for field in zona._meta.fields:
        if any(k in field.name for k in ('tiempo', 'min', 'duracion')):
            val = getattr(zona, field.name, None)
            if isinstance(val, int) and val > 0:
                return val
    return None


def calcular_tiempo_estimado(sede, lineas, tipo_entrega='domicilio', direccion=None):
    """Devuelve los minutos estimados para entregar el pedido (HU32)."""
    tiempos_prod = []
    for linea in lineas:
        prod = linea['producto']
        t = (
            getattr(prod, 'prep_time_minutes', None)
            or getattr(prod, 'prep_time', None)
            or getattr(prod, 'tiempo_preparacion', None)
            or TIEMPO_BASE_PREPARACION
        )
        tiempos_prod.append(int(t))
    prep = max(tiempos_prod) if tiempos_prod else TIEMPO_BASE_PREPARACION

    recargo_cocina = 0
    cap = estado_capacidad(sede)
    if cap is not None:
        if cap.porcentaje >= 80:
            recargo_cocina = 15
        elif cap.porcentaje >= 50:
            recargo_cocina = 10
        elif cap.ocupados > 0:
            recargo_cocina = 5

    traslado = 0
    if tipo_entrega == 'domicilio':
        traslado = TIEMPO_BASE_DOMICILIO
        if direccion is not None and ZonaCobertura.tiene_zonas(sede):
            zona = ZonaCobertura.para_direccion(sede, direccion)
            if zona is not None:
                t_zona = _minutos_zona(zona)
                if t_zona:
                    traslado = t_zona

    return prep + recargo_cocina + traslado