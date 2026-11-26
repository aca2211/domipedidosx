"""Cobertura de domicilios por zona (HU24, HU25).

HU24: cada zona de la sede tiene tarifa de domicilio, tiempo estimado y pedido mínimo.
HU25: `verificar_cobertura` rechaza el pedido si la dirección no cae en ninguna zona
      de la sede o si el subtotal no llega al mínimo de la zona.

Si la sede no tiene zonas activas no hay restricción y el domicilio cuesta COSTO_DOMICILIO.
"""
from menu.models import Sede, ZonaCobertura
from .cart import COSTO_DOMICILIO, CarritoError


class CoberturaError(CarritoError):
    """La dirección no tiene cobertura o el pedido no alcanza el mínimo (HU25).

    Hereda de CarritoError para que las vistas existentes la capturen sin cambios.
    """


def _pesos(valor):
    return '$' + f'{valor:,.0f}'.replace(',', '.')


def _mensaje_fuera(sede, direccion):
    barrios = []
    for zona in ZonaCobertura.objects.filter(sede=sede, is_active=True):
        barrios.extend(zona.lista_barrios)
    texto = f'La dirección «{direccion.label}» está fuera de la cobertura de la sede {sede.name}.'
    if barrios:
        texto += f' Barrios con cobertura: {", ".join(barrios)}.'
    otras = [
        s.name for s in Sede.objects.filter(is_active=True).exclude(pk=sede.pk).order_by('name')
        if ZonaCobertura.para_direccion(s, direccion)
    ]
    if otras:
        texto += f' Esa dirección sí tiene cobertura en: {", ".join(otras)}.'
    return texto


def evaluar_cobertura(sede, direccion, subtotal):
    """Devuelve (costo_domicilio, mensaje_de_error). El mensaje es None si todo está bien."""
    if direccion is None or not ZonaCobertura.tiene_zonas(sede):
        return COSTO_DOMICILIO, None
    zona = ZonaCobertura.para_direccion(sede, direccion)
    if zona is None:
        return COSTO_DOMICILIO, _mensaje_fuera(sede, direccion)
    minimo = zona.minimo_efectivo()
    if subtotal < minimo:
        return zona.tarifa_domicilio, (
            f'El pedido mínimo para la zona {zona.nombre} es {_pesos(minimo)}. '
            f'Tu subtotal es {_pesos(subtotal)}: agrega más productos.'
        )
    return zona.tarifa_domicilio, None


def verificar_cobertura(sede, direccion, subtotal):
    """Devuelve el costo de domicilio de la dirección o lanza CoberturaError (HU24 + HU25)."""
    costo, error = evaluar_cobertura(sede, direccion, subtotal)
    if error:
        raise CoberturaError(error)
    return costo


def evaluar_direcciones(sede, direcciones, subtotal):
    """Costo y aviso de cada dirección, para mostrarlos en pantalla antes de confirmar.

    Devuelve {'subtotal': ..., 'direcciones': {id: {'costo': ..., 'aviso': texto o None}}}.
    """
    resultado = {}
    for d in direcciones:
        costo, aviso = evaluar_cobertura(sede, d, subtotal)
        resultado[str(d.pk)] = {'costo': float(costo), 'aviso': aviso}
    return {'subtotal': float(subtotal), 'direcciones': resultado}
