"""python manage.py cargar_demo

Crea datos para la presentación: 2 sedes, 3 categorías, 10 productos con su
disponibilidad por sede, un usuario por rol y unos pedidos de ejemplo en
distintos estados. Se puede correr varias veces sin duplicar nada.
"""
from datetime import time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from menu.models import Category, Product, Sede, SedeProduct
from pedidos.cart import COSTO_DOMICILIO
from pedidos.models import DetallePedido, Pedido
from users.models import Direccion

User = get_user_model()

PASSWORD = 'demo1234'

SEDES = [
    # (nombre, dirección, apertura, cierre)
    ('Sede Centro', 'Cra 5 # 12-30, Centro', time(7, 0), time(23, 0)),
    ('Sede Norte', 'Av 6N # 25-10, Norte', time(10, 0), time(22, 0)),
]

CATEGORIAS = [
    ('Hamburguesas', 'Hamburguesas artesanales con papas'),
    ('Bebidas', 'Bebidas frías y malteadas'),
    ('Acompañamientos', 'Para compartir o acompañar'),
]

PRODUCTOS = [
    # (categoría, nombre, descripción, precio, minutos de preparación)
    ('Hamburguesas', 'Hamburguesa Clásica', 'Carne de res, queso, lechuga y tomate', '18000', 15),
    ('Hamburguesas', 'Hamburguesa Doble Carne', 'Doble carne, doble queso y salsa de la casa', '24000', 18),
    ('Hamburguesas', 'Hamburguesa Pollo Crispy', 'Pollo apanado, lechuga y mayonesa', '20000', 15),
    ('Hamburguesas', 'Hamburguesa Vegetariana', 'Medallón de lentejas, aguacate y tomate', '19000', 15),
    ('Bebidas', 'Limonada Natural', 'Limonada recién exprimida', '6000', 5),
    ('Bebidas', 'Gaseosa', 'Gaseosa personal 400 ml', '4500', 2),
    ('Bebidas', 'Malteada de Chocolate', 'Helado de vainilla y chocolate', '12000', 8),
    ('Acompañamientos', 'Papas Fritas', 'Porción grande con sal marina', '8000', 10),
    ('Acompañamientos', 'Aros de Cebolla', 'Aros apanados con salsa BBQ', '9000', 10),
    ('Acompañamientos', 'Ensalada de la Casa', 'Lechuga, tomate, zanahoria y vinagreta', '10000', 8),
]

# Productos agotados en una sede, para mostrar la disponibilidad por sede.
AGOTADOS = {('Sede Norte', 'Malteada de Chocolate')}

USUARIOS = [
    # (usuario, rol, nombre, apellido)
    ('demo_cliente', 'cliente', 'Ana', 'Cliente'),
    ('demo_operador', 'operador', 'Oscar', 'Operador'),
    ('demo_cocina', 'cocina', 'Carla', 'Cocina'),
    ('demo_admin', 'admin', 'Adriana', 'Admin'),
]

PEDIDOS = [
    # (sede, estado, entrega, pago, observaciones, [(producto, cantidad)], minutos atrás)
    ('Sede Centro', 'recibido', 'domicilio', 'efectivo', 'Sin cebolla, por favor',
     [('Hamburguesa Clásica', 2), ('Gaseosa', 2)], 4),
    ('Sede Centro', 'recibido', 'mostrador', 'tarjeta', '',
     [('Hamburguesa Pollo Crispy', 1), ('Limonada Natural', 1)], 9),
    ('Sede Centro', 'en_preparacion', 'domicilio', 'transferencia', 'Llamar al llegar',
     [('Hamburguesa Doble Carne', 1), ('Papas Fritas', 1), ('Malteada de Chocolate', 1)], 18),
    ('Sede Centro', 'listo', 'mostrador', 'efectivo', '',
     [('Hamburguesa Vegetariana', 1), ('Ensalada de la Casa', 1)], 27),
    ('Sede Centro', 'entregado', 'domicilio', 'tarjeta', '',
     [('Hamburguesa Clásica', 1), ('Aros de Cebolla', 1)], 45),
    ('Sede Centro', 'cancelado', 'domicilio', 'efectivo', 'Cambié de opinión',
     [('Papas Fritas', 1)], 35),
    ('Sede Norte', 'recibido', 'mostrador', 'efectivo', '',
     [('Hamburguesa Clásica', 1), ('Gaseosa', 1)], 6),
]


class Command(BaseCommand):
    help = 'Carga datos de demostración (sedes, menú, usuarios por rol y pedidos de ejemplo).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reiniciar-pedidos', action='store_true',
            help='Borra los pedidos del cliente demo y los vuelve a crear.',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Permite correr el comando con DEBUG=False (no lo uses en producción).',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force']:
            raise CommandError(
                'cargar_demo crea usuarios con contraseña conocida y solo debe usarse en desarrollo '
                '(DEBUG=True). Si de verdad lo necesitas, agrega --force.'
            )
        with transaction.atomic():
            sedes = self._sedes()
            productos = self._menu(sedes)
            usuarios = self._usuarios()
            self._direccion(usuarios['cliente'])
            self._pedidos(usuarios, sedes, productos, options['reiniciar_pedidos'])
        self._resumen()

    # ---------- sedes, categorías y productos ----------
    def _sedes(self):
        sedes = {}
        for nombre, direccion, apertura, cierre in SEDES:
            sede, _ = Sede.objects.get_or_create(
                name=nombre,
                defaults={'address': direccion, 'opening_time': apertura, 'closing_time': cierre},
            )
            sedes[nombre] = sede
        self.stdout.write(f'Sedes: {len(sedes)}')
        return sedes

    def _menu(self, sedes):
        categorias = {
            nombre: Category.objects.get_or_create(name=nombre, defaults={'description': desc})[0]
            for nombre, desc in CATEGORIAS
        }
        productos = {}
        for categoria, nombre, descripcion, precio, minutos in PRODUCTOS:
            producto, _ = Product.objects.get_or_create(
                name=nombre,
                defaults={
                    'category': categorias[categoria], 'description': descripcion,
                    'price': Decimal(precio), 'prep_time_minutes': minutos,
                },
            )
            productos[nombre] = producto
            for nombre_sede, sede in sedes.items():
                SedeProduct.objects.get_or_create(
                    sede=sede, product=producto,
                    defaults={'is_available': (nombre_sede, nombre) not in AGOTADOS},
                )
        self.stdout.write(f'Categorías: {len(categorias)} · Productos: {len(productos)}')
        return productos

    # ---------- usuarios ----------
    def _usuarios(self):
        usuarios = {}
        for username, rol, nombre, apellido in USUARIOS:
            usuario, creado = User.objects.get_or_create(
                username=username,
                defaults={
                    'role': rol, 'first_name': nombre, 'last_name': apellido,
                    'email': f'{username}@demo.com', 'phone': '3001234567',
                },
            )
            if creado:
                usuario.set_password(PASSWORD)
            if rol == 'admin':
                usuario.is_staff = usuario.is_superuser = True
            elif rol == 'operador':
                usuario.is_staff = True  # el panel del operador enlaza al admin (menú y pedidos)
            usuario.save()
            usuarios[rol] = usuario
        self._permisos_operador(usuarios['operador'])
        self.stdout.write(f'Usuarios demo: {len(usuarios)}')
        return usuarios

    def _permisos_operador(self, operador):
        """El operador gestiona el menú y consulta los pedidos, nada más."""
        permisos = Permission.objects.filter(content_type__app_label='menu') | Permission.objects.filter(
            content_type__app_label='pedidos', codename__in=['view_pedido', 'view_detallepedido'],
        )
        operador.user_permissions.set(permisos)

    def _direccion(self, cliente):
        Direccion.objects.get_or_create(
            user=cliente, label='Casa',
            defaults={'address': 'Calle 10 # 4-25, Apto 301', 'details': 'Portería 24 h', 'is_default': True},
        )

    # ---------- pedidos de ejemplo ----------
    def _pedidos(self, usuarios, sedes, productos, reiniciar):
        cliente = usuarios['cliente']
        if reiniciar:
            Pedido.objects.filter(cliente=cliente).delete()
        if Pedido.objects.filter(cliente=cliente).exists():
            self.stdout.write('Pedidos de ejemplo: ya existen, no se duplican.')
            return

        direccion = Direccion.objects.get(user=cliente, is_default=True)
        ahora = timezone.localtime()
        # Los pedidos de "hoy": ninguno se fecha antes de las 00:01, aunque corras esto de madrugada.
        inicio_dia = ahora.replace(hour=0, minute=1, second=0, microsecond=0)

        for nombre_sede, estado, entrega, pago, notas, items, minutos in PEDIDOS:
            lineas = [(productos[nombre], cantidad) for nombre, cantidad in items]
            subtotal = sum((p.price * c for p, c in lineas), Decimal('0'))
            costo = COSTO_DOMICILIO if entrega == 'domicilio' else Decimal('0')
            pedido = Pedido.objects.create(
                cliente=cliente, creado_por=usuarios['operador'] if entrega == 'mostrador' else cliente,
                sede=sedes[nombre_sede], tipo_entrega=entrega,
                direccion=direccion if entrega == 'domicilio' else None,
                metodo_pago=pago, observaciones=notas,
                subtotal=subtotal, costo_domicilio=costo, total=subtotal + costo, estado=estado,
            )
            DetallePedido.objects.bulk_create([
                DetallePedido(
                    pedido=pedido, producto=p, cantidad=c,
                    precio_unitario=p.price, subtotal=p.price * c,
                )
                for p, c in lineas
            ])
            momento = max(ahora - timedelta(minutes=minutos), inicio_dia)
            Pedido.objects.filter(pk=pedido.pk).update(created_at=momento)
        self.stdout.write(f'Pedidos de ejemplo: {len(PEDIDOS)}')

    def _resumen(self):
        self.stdout.write(self.style.SUCCESS('\nDatos de demostración listos.'))
        self.stdout.write(f'Contraseña de todos los usuarios demo: {PASSWORD}')
        for username, rol, _, _ in USUARIOS:
            self.stdout.write(f'  {rol:<9} {username}')
