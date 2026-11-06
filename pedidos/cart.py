"""Carrito de compras guardado en la sesión (HU13). No usa modelos propios."""
from decimal import Decimal

from menu.models import Product, Sede, SedeProduct

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


class Carrito:
    def __init__(self, request):
        self.session = request.session
        data = self.session.get(SESSION_KEY) or {}
        self.sede_id = data.get('sede_id')
        self.items = {int(k): int(v) for k, v in (data.get('items') or {}).items()}


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

    def resumen(self):
        """Líneas con precio actual, disponibilidad en la sede y totales."""
        ids = list(self.items)
        productos = {p.id: p for p in Product.objects.filter(pk__in=ids).select_related('category')}
        disponibles = set()
        if self.sede_id and ids:
            disponibles = set(
                SedeProduct.objects.filter(
                    sede_id=self.sede_id, sede__is_active=True,
                    product_id__in=ids, is_available=True,
                ).values_list('product_id', flat=True)
            )
        lineas = []
        for pid, cantidad in self.items.items():
            producto = productos.get(pid)
            if producto is None:
                continue
            lineas.append({
                'producto': producto,
                'cantidad': cantidad,
                'precio': producto.price,
                'subtotal': producto.price * cantidad,
                'disponible': pid in disponibles,
            })
        lineas.sort(key=lambda l: l['producto'].name)
        subtotal = sum((l['subtotal'] for l in lineas), Decimal('0'))
        return {
            'lineas': lineas,
            'subtotal': subtotal,
            'costo_domicilio': COSTO_DOMICILIO,
            'total': subtotal + COSTO_DOMICILIO,
            'hay_agotados': any(not l['disponible'] for l in lineas),
            'hay_faltantes': len(lineas) != len(self.items),
        }


    def agregar(self, producto_id, sede_id, cantidad=1):
        """Agrega un producto. Devuelve True si cambió de sede y el carrito se vació."""
        cantidad = validar_cantidad(cantidad)
        sede = Sede.objects.filter(pk=sede_id, is_active=True).first()
        if sede is None:
            raise CarritoError('La sede elegida no está disponible.')
        producto = Product.objects.filter(pk=producto_id).first()
        if producto is None:
            raise CarritoError('El producto no existe.')
        if not SedeProduct.objects.filter(sede=sede, product=producto, is_available=True).exists():
            raise CarritoError(f'«{producto.name}» no está disponible en la sede {sede.name}.')

        nuevo_total = self.items.get(producto.id, 0) + cantidad
        if nuevo_total > CANTIDAD_MAXIMA:
            raise CarritoError(f'La cantidad máxima por producto es {CANTIDAD_MAXIMA}.')

        cambio_sede = False
        if self.sede_id != sede.id:
            cambio_sede = bool(self.items)
            self.items = {}
            self.sede_id = sede.id
        self.items[producto.id] = nuevo_total
        self._guardar()
        return cambio_sede

    def actualizar(self, producto_id, cantidad):
        cantidad = validar_cantidad(cantidad)
        if producto_id not in self.items:
            raise CarritoError('Ese producto no está en tu carrito.')
        self.items[producto_id] = cantidad
        self._guardar()

    def quitar(self, producto_id):
        self.items.pop(producto_id, None)
        if not self.items:
            self.sede_id = None
        self._guardar()

    def vaciar(self):
        self.items = {}
        self.sede_id = None
        self.session.pop(SESSION_KEY, None)
        self.session.modified = True