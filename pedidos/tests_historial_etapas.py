"""HU43: registro de la hora en que cada pedido entra a cada estado."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from menu.models import Category, Product, Sede, SedeProduct

from .cart import Carrito
from .models import HistorialEstado, Pedido
from .services import avanzar_pedido, cancelar_pedido, crear_pedido, tiempos_por_etapa

User = get_user_model()


class FakeSession(dict):
    modified = False


class FakeRequest:
    def __init__(self):
        self.session = FakeSession()


class HistorialEtapasTests(TestCase):
    def setUp(self):
        self.cliente = User.objects.create_user('ana', password='x', role='cliente')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        cat = Category.objects.create(name='Comidas')
        self.burger = Product.objects.create(category=cat, name='Burger', description='d', price=Decimal('15000'))
        SedeProduct.objects.create(sede=self.sede, product=self.burger, stock=10, stock_minimo=0)
        patcher = patch.object(Sede, 'is_open_now', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def crear(self):
        carrito = Carrito(FakeRequest())
        carrito.agregar(self.burger.id, self.sede.id, 1)
        return crear_pedido(carrito, self.cliente, 'efectivo', tipo_entrega='mostrador')

    def estados(self, pedido):
        return list(pedido.historial_estados.values_list('estado', flat=True))

    def test_al_crear_el_pedido_registra_recibido(self):
        pedido = self.crear()
        self.assertEqual(self.estados(pedido), ['recibido'])

    def test_cada_avance_registra_una_entrada_en_orden(self):
        pedido = self.crear()
        avanzar_pedido(pedido.pk, self.sede, 'recibido')
        avanzar_pedido(pedido.pk, self.sede, 'en_preparacion')
        avanzar_pedido(pedido.pk, self.sede, 'listo')
        self.assertEqual(self.estados(pedido), ['recibido', 'en_preparacion', 'listo', 'entregado'])

    def test_cancelar_registra_cancelado(self):
        pedido = self.crear()
        cancelar_pedido(pedido.pk, self.cliente)
        self.assertEqual(self.estados(pedido), ['recibido', 'cancelado'])

    def test_un_avance_fallido_no_registra_nada(self):
        pedido = self.crear()
        with self.assertRaises(Exception):
            avanzar_pedido(pedido.pk, self.sede, 'listo')  # no es el estado esperado
        self.assertEqual(self.estados(pedido), ['recibido'])

    def test_tiempos_por_etapa_calcula_la_duracion_de_cada_una(self):
        pedido = self.crear()
        base = timezone.now()
        HistorialEstado.objects.filter(pedido=pedido).delete()
        HistorialEstado.objects.create(pedido=pedido, estado='recibido', entrada=base)
        HistorialEstado.objects.create(pedido=pedido, estado='en_preparacion', entrada=base + timedelta(minutes=5))
        HistorialEstado.objects.create(pedido=pedido, estado='listo', entrada=base + timedelta(minutes=20))
        tiempos = tiempos_por_etapa(pedido)
        self.assertEqual([t['estado'] for t in tiempos], ['recibido', 'en_preparacion'])
        self.assertEqual([t['minutos'] for t in tiempos], [5.0, 15.0])

    def test_pedido_sin_avances_no_tiene_tiempos_completos(self):
        pedido = self.crear()
        self.assertEqual(tiempos_por_etapa(pedido), [])

    def test_la_etapa_actual_no_tiene_fin_todavia(self):
        pedido = self.crear()
        avanzar_pedido(pedido.pk, self.sede, 'recibido')
        tiempos = tiempos_por_etapa(pedido)
        self.assertEqual([t['estado'] for t in tiempos], ['recibido'])
        self.assertNotIn('en_preparacion', [t['estado'] for t in tiempos])
