"""HU31: correos al cliente al confirmar, cambiar de estado o cancelar un pedido."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from menu.models import Category, Product, Sede, SedeProduct

from .cart import Carrito, CarritoError
from .services import AvanceError, avanzar_pedido, cancelar_pedido, crear_pedido

User = get_user_model()


class FakeSession(dict):
    modified = False


class FakeRequest:
    def __init__(self):
        self.session = FakeSession()


class NotificacionesPedidoTests(TestCase):
    def setUp(self):
        self.cliente = User.objects.create_user(
            'ana', password='x', role='cliente', email='ana@test.com', first_name='Ana')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        cat = Category.objects.create(name='Comidas')
        self.burger = Product.objects.create(category=cat, name='Burger', description='d', price=Decimal('15000'))
        SedeProduct.objects.create(sede=self.sede, product=self.burger, stock=10, stock_minimo=0)

    def crear(self):
        carrito = Carrito(FakeRequest())
        carrito.agregar(self.burger.id, self.sede.id, 1)
        with self.captureOnCommitCallbacks(execute=True):
            return crear_pedido(carrito, self.cliente, 'efectivo', tipo_entrega='mostrador')

    def test_confirmar_envia_correo_al_cliente(self):
        pedido = self.crear()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana@test.com'])
        self.assertIn(f'Pedido #{pedido.pk} confirmado', mail.outbox[0].subject)
        self.assertIn('Centro', mail.outbox[0].body)

    def test_cambio_de_estado_envia_correo(self):
        pedido = self.crear()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            avanzar_pedido(pedido.pk, self.sede, 'recibido')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('en preparacion', mail.outbox[0].subject.lower())

    def test_cancelar_envia_correo(self):
        pedido = self.crear()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            cancelar_pedido(pedido.pk, self.cliente)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('cancelado', mail.outbox[0].subject)

    def test_cliente_sin_correo_no_recibe_nada(self):
        self.cliente.email = ''
        self.cliente.save()
        self.crear()
        self.assertEqual(len(mail.outbox), 0)

    def test_avance_fallido_no_envia_correo(self):
        pedido = self.crear()
        mail.outbox.clear()
        with self.assertRaises(AvanceError):
            with self.captureOnCommitCallbacks(execute=True):
                avanzar_pedido(pedido.pk, self.sede, 'listo')
        self.assertEqual(len(mail.outbox), 0)

    def test_error_al_enviar_no_rompe_el_pedido(self):
        with patch('pedidos.notificaciones.send_mail', side_effect=OSError('smtp caído')):
            pedido = self.crear()
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'recibido')
        self.assertEqual(len(mail.outbox), 0)
