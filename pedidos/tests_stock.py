"""HU29 (existencias y bloqueo al agotarse) y HU30 (alerta de stock bajo el mínimo)."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from menu.models import Category, Product, Sede, SedeProduct

from .cart import Carrito, CarritoError
from .models import Pedido
from .services import cancelar_pedido, crear_pedido, productos_bajo_minimo

User = get_user_model()


class FakeSession(dict):
    modified = False


class FakeRequest:
    def __init__(self):
        self.session = FakeSession()


class StockTests(TestCase):
    def setUp(self):
        self.cliente = User.objects.create_user('ana', password='x', role='cliente')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        cat = Category.objects.create(name='Comidas')
        self.burger = Product.objects.create(category=cat, name='Burger', description='d', price=Decimal('15000'))
        self.sp = SedeProduct.objects.create(sede=self.sede, product=self.burger, stock=5, stock_minimo=2)
        # La sede de prueba debe estar abierta para que crear_pedido no falle por horario
        patcher = patch.object(Sede, 'is_open_now', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def carrito_con(self, cantidad):
        carrito = Carrito(FakeRequest())
        carrito.agregar(self.burger.id, self.sede.id, cantidad)
        return carrito

    def pedir(self, cantidad):
        return crear_pedido(self.carrito_con(cantidad), self.cliente, 'efectivo', tipo_entrega='mostrador')

    def stock_actual(self):
        self.sp.refresh_from_db()
        return self.sp.stock

    # --- HU29 ---

    def test_sin_control_de_stock_no_descuenta_ni_bloquea(self):
        self.sp.stock = None
        self.sp.save()
        self.pedir(3)
        self.sp.refresh_from_db()
        self.assertIsNone(self.sp.stock)
        self.assertTrue(self.sp.is_available)

    def test_crear_pedido_descuenta_existencias(self):
        self.pedir(2)
        self.assertEqual(self.stock_actual(), 3)

    def test_agotarse_bloquea_el_producto_automaticamente(self):
        self.pedir(5)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.stock, 0)
        self.assertFalse(self.sp.is_available)

    def test_no_alcanza_el_stock_no_crea_pedido_ni_descuenta(self):
        with self.assertRaises(CarritoError):
            self.pedir(6)
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(self.stock_actual(), 5)

    def test_cancelar_devuelve_las_existencias(self):
        pedido = self.pedir(2)
        cancelar_pedido(pedido.pk, self.cliente)
        self.assertEqual(self.stock_actual(), 5)

    def test_reponer_un_producto_agotado_lo_vuelve_disponible(self):
        self.pedir(5)
        self.sp.refresh_from_db()
        self.sp.reponer(4)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.stock, 4)
        self.assertTrue(self.sp.is_available)

    def test_stock_cero_desde_admin_bloquea_el_producto(self):
        self.sp.stock = 0
        self.sp.save()
        self.sp.refresh_from_db()
        self.assertFalse(self.sp.is_available)

    # --- HU30 ---

    def test_alerta_cuando_llega_al_minimo(self):
        self.sp.stock = 2  # igual al mínimo (2)
        self.sp.save()
        self.assertTrue(self.sp.bajo_minimo)
        self.assertIn(self.sp, productos_bajo_minimo(self.sede))

    def test_sin_alerta_por_encima_del_minimo(self):
        self.assertFalse(self.sp.bajo_minimo)
        self.assertNotIn(self.sp, productos_bajo_minimo(self.sede))

    def test_sin_control_de_stock_no_genera_alerta(self):
        self.sp.stock = None
        self.sp.save()
        self.assertFalse(self.sp.bajo_minimo)
        self.assertNotIn(self.sp, productos_bajo_minimo(self.sede))

    def test_alertas_ordenadas_de_mas_criticas_a_menos(self):
        papas = Product.objects.create(category=self.burger.category, name='Papas', description='d', price=Decimal('8000'))
        sp_papas = SedeProduct.objects.create(sede=self.sede, product=papas, stock=1, stock_minimo=3)
        self.sp.stock = 2
        self.sp.save()
        self.assertEqual(list(productos_bajo_minimo(self.sede)), [sp_papas, self.sp])
