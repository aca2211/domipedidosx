"""Carrito de compras guardado en la sesión (HU13). No usa modelos propios."""
from decimal import Decimal

from menu.models import Product, ProductOption, Sede, SedeProduct, ZonaCobertura

SESSION_KEY = 'carrito'
COSTO_DOMICILIO = Decimal('0') 
CANTIDAD_MINIMA = 1
CANTIDAD_MAXIMA = 50


class CarritoError(Exception):
    """Error de regla de negocio del carrito; el mensaje es apto para el usuario."""


def validar_cantidad(valor):
    try:
        cantidad = int(valor)
    except (TypeError, ValueError):
        raise CarritoError('La cantidad no es válida.')
    if cantidad < CANTIDAD_MINIMA:
        raise CarritoError(f'La cantidad mínima es {CANTIDAD_MINIMA}.')
    if cantidad > CANTIDAD_MAXIMA:
        raise CarritoError(f'La cantidad máxima por producto es {CANTIDAD_MAXIMA}.')
    return cantidad


def clave_linea(producto_id, opcion_ids=()):
    """Identifica una línea del carrito: «12» si no tiene opciones, «12-5-8» con las opciones 5 y 8 (HU10).

    Un mismo producto con distintas opciones son líneas distintas.
    """
    return '-'.join([str(producto_id)] + [str(i) for i in sorted(set(opcion_ids))])


def separar_clave(clave):
    """Devuelve (producto_id, [opcion_ids]) o None si la clave no es válida."""
    try:
        producto_id, *opciones = [int(x) for x in str(clave).split('-')]
    except ValueError:
        return None
    return producto_id, opciones


def describir_opcion(opcion):
    return {
        'kind': opcion.kind,
        'name': opcion.name,
        'extra': opcion.extra_price,
        'con_recargo': opcion.extra_price > 0,
    }


class Carrito:
    def __init__(self, request):
        self.session = request.session
        data = self.session.get(SESSION_KEY) or {}
        self.sede_id = data.get('sede_id')
        # clave de línea -> cantidad (la clave lleva el producto y sus opciones, ver clave_linea)
        self.items = {str(k): int(v) for k, v in (data.get('items') or {}).items()}


    def _guardar(self):
        self.session[SESSION_KEY] = {
            'sede_id': self.sede_id,
            'items': {str(k): v for k, v in self.items.items()},
        }
        self.session.modified = True


    @property
    def vacio(self):
        return not self.items

    def __len__(self):
        return sum(self.items.values())

    @property
    def sede(self):
        return Sede.objects.filter(pk=self.sede_id).first() if self.sede_id else None

    def _costo_domicilio(self, direccion):
        """Tarifa de la zona que cubre la dirección (HU24); sin zona o sin dirección, el costo por defecto."""
        if direccion is None:
            return COSTO_DOMICILIO
        zona = ZonaCobertura.para_direccion(self.sede, direccion)
        return zona.tarifa_domicilio if zona else COSTO_DOMICILIO

    def resumen(self, direccion=None):
        """Líneas con precio actual (base + recargos de opciones), disponibilidad en la sede y totales.

        Con `direccion` el domicilio se cobra según su zona (HU24); sin ella, no se puede saber.
        """
        partes = {clave: separar_clave(clave) for clave in self.items}
        ids = {p[0] for p in partes.values() if p}
        opcion_ids = {i for p in partes.values() if p for i in p[1]}
        productos = {p.id: p for p in Product.objects.filter(pk__in=ids).select_related('category')}
        opciones = {o.id: o for o in ProductOption.objects.filter(pk__in=opcion_ids, is_active=True)}
        disponibles = set()
        if self.sede_id and ids:
            disponibles = set(
                SedeProduct.objects.filter(
                    sede_id=self.sede_id, sede__is_active=True,
                    product_id__in=ids, is_available=True,
                ).values_list('product_id', flat=True)
            )
        lineas = []
        for clave, cantidad in self.items.items():
            pid, ops = partes[clave] or (None, [])
            producto = productos.get(pid)
            if producto is None:
                continue
            elegidas = [opciones[i] for i in ops if i in opciones and opciones[i].product_id == pid]
            precio = producto.price + sum((o.extra_price for o in elegidas), Decimal('0'))
            lineas.append({
                'clave': clave,
                'producto': producto,
                'cantidad': cantidad,
                'precio': precio,
                'subtotal': precio * cantidad,
                'disponible': pid in disponibles,
                'opciones': [describir_opcion(o) for o in elegidas],
                # True si alguna opción de la línea se desactivó o se borró desde que se agregó
                'opciones_invalidas': len(elegidas) != len(ops),
            })
        lineas.sort(key=lambda l: (l['producto'].name, l['clave']))
        subtotal = sum((l['subtotal'] for l in lineas), Decimal('0'))
        costo_domicilio = self._costo_domicilio(direccion)
        return {
            'lineas': lineas,
            'subtotal': subtotal,
            'costo_domicilio': costo_domicilio,
            'total': subtotal + costo_domicilio,
            # True si el domicilio depende de la zona: en el carrito aún no se conoce la dirección
            'domicilio_por_zona': ZonaCobertura.tiene_zonas(self.sede),
            'hay_agotados': any(not l['disponible'] for l in lineas),
            'hay_faltantes': len(lineas) != len(self.items),
            'hay_opciones_invalidas': any(l['opciones_invalidas'] for l in lineas),
        }

    def _validar_opciones(self, producto, opcion_ids):
        """Comprueba que las opciones sean activas y de ese producto y que haya un solo tamaño (HU10)."""
        ids = set(opcion_ids)
        validas = {o.id: o for o in producto.options.filter(is_active=True)}
        if not ids <= validas.keys():
            raise CarritoError(f'Alguna opción elegida no está disponible para «{producto.name}».')
        tamanos_elegidos = [i for i in ids if validas[i].kind == ProductOption.SIZE]
        hay_tamanos = any(o.kind == ProductOption.SIZE for o in validas.values())
        if len(tamanos_elegidos) > 1:
            raise CarritoError('Elige un solo tamaño.')
        if hay_tamanos and not tamanos_elegidos:
            raise CarritoError(f'Elige un tamaño para «{producto.name}».')
        return sorted(ids)

    def agregar(self, producto_id, sede_id, cantidad=1, opcion_ids=()):
        """Agrega un producto con sus opciones. Devuelve True si cambió de sede y el carrito se vació."""
        cantidad = validar_cantidad(cantidad)
        sede = Sede.objects.filter(pk=sede_id, is_active=True).first()
        if sede is None:
            raise CarritoError('La sede elegida no está disponible.')
        producto = Product.objects.filter(pk=producto_id).first()
        if producto is None:
            raise CarritoError('El producto no existe.')
        if not SedeProduct.objects.filter(sede=sede, product=producto, is_available=True).exists():
            raise CarritoError(f'«{producto.name}» no está disponible en la sede {sede.name}.')
        opcion_ids = self._validar_opciones(producto, opcion_ids)

        clave = clave_linea(producto.id, opcion_ids)
        nuevo_total = self.items.get(clave, 0) + cantidad
        if nuevo_total > CANTIDAD_MAXIMA:
            raise CarritoError(f'La cantidad máxima por producto es {CANTIDAD_MAXIMA}.')

        cambio_sede = False
        if self.sede_id != sede.id:
            cambio_sede = bool(self.items)
            self.items = {}
            self.sede_id = sede.id
        self.items[clave] = nuevo_total
        self._guardar()
        return cambio_sede

    def actualizar(self, clave, cantidad):
        cantidad = validar_cantidad(cantidad)
        if clave not in self.items:
            raise CarritoError('Ese producto no está en tu carrito.')
        self.items[clave] = cantidad
        self._guardar()

    def quitar(self, clave):
        self.items.pop(clave, None)
        if not self.items:
            self.sede_id = None
        self._guardar()

    def vaciar(self):
        self.items = {}
        self.sede_id = None
        self.session.pop(SESSION_KEY, None)
        self.session.modified = True
