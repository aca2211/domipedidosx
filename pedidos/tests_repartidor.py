from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from menu.models import Sede
from .models import Pedido

User = get_user_model()


class AsignarRepartidorTests(TestCase):  # HU22
    def setUp(self):
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        self.otra_sede = Sede.objects.create(name='Norte', address='Av 3')
        self.operador = User.objects.create_user('ope', password='x', role='operador', sede=self.sede)
        self.cliente = User.objects.create_user('cli', password='x', role='cliente')
        self.repartidor = User.objects.create_user('rep1', password='x', role='repartidor', sede=self.sede)
        self.client.force_login(self.operador)

    def _crear_pedido(self, estado='listo', tipo_entrega='domicilio', sede=None):
        return Pedido.objects.create(
            cliente=self.cliente,
            creado_por=self.cliente,
            sede=sede or self.sede,
            tipo_entrega=tipo_entrega,
            metodo_pago='efectivo',
            subtotal=Decimal('25000'),
            total=Decimal('25000'),
            estado=estado,
        )

    def test_asignar_repartidor_cambia_a_en_camino(self):
        pedido = self._crear_pedido(estado='listo')
        r = self.client.post(
            reverse('operador_asignar_repartidor', args=[pedido.pk]),
            {'repartidor_id': self.repartidor.pk},
        )
        self.assertRedirects(r, reverse('operador_panel'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.repartidor, self.repartidor)
        self.assertEqual(pedido.estado, 'en_camino')

    def test_no_asigna_si_no_esta_listo(self):
        pedido = self._crear_pedido(estado='en_preparacion')
        self.client.post(
            reverse('operador_asignar_repartidor', args=[pedido.pk]),
            {'repartidor_id': self.repartidor.pk},
        )
        pedido.refresh_from_db()
        self.assertIsNone(pedido.repartidor)
        self.assertEqual(pedido.estado, 'en_preparacion')

    def test_no_asigna_si_es_mostrador(self):
        pedido = self._crear_pedido(estado='listo', tipo_entrega='mostrador')
        self.client.post(
            reverse('operador_asignar_repartidor', args=[pedido.pk]),
            {'repartidor_id': self.repartidor.pk},
        )
        pedido.refresh_from_db()
        self.assertIsNone(pedido.repartidor)
        self.assertEqual(pedido.estado, 'listo')

    def test_no_asigna_usuario_sin_rol_repartidor(self):
        pedido = self._crear_pedido(estado='listo')
        self.client.post(
            reverse('operador_asignar_repartidor', args=[pedido.pk]),
            {'repartidor_id': self.cliente.pk},
        )
        pedido.refresh_from_db()
        self.assertIsNone(pedido.repartidor)
        self.assertEqual(pedido.estado, 'listo')

    def test_no_toca_pedidos_de_otra_sede(self):
        pedido = self._crear_pedido(estado='listo', sede=self.otra_sede)
        r = self.client.post(
            reverse('operador_asignar_repartidor', args=[pedido.pk]),
            {'repartidor_id': self.repartidor.pk},
        )
        self.assertEqual(r.status_code, 404)