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


class PanelRepartidorTests(TestCase):  # HU23
    def setUp(self):
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        self.cliente = User.objects.create_user('cli', password='x', role='cliente')
        self.repartidor = User.objects.create_user('rep1', password='x', role='repartidor', sede=self.sede)
        self.otro_rep = User.objects.create_user('rep2', password='x', role='repartidor', sede=self.sede)
        self.client.force_login(self.repartidor)

    def _crear_pedido(self, repartidor=None, estado='en_camino'):
        return Pedido.objects.create(
            cliente=self.cliente,
            creado_por=self.cliente,
            repartidor=repartidor or self.repartidor,
            sede=self.sede,
            tipo_entrega='domicilio',
            metodo_pago='efectivo',
            subtotal=Decimal('30000'),
            total=Decimal('30000'),
            estado=estado,
        )

    def test_otros_roles_reciben_403(self):
        for username, role in [('c1', 'cliente'), ('o1', 'operador'), ('k1', 'cocina')]:
            self.client.force_login(User.objects.create_user(username, password='x', role=role))
            self.assertEqual(self.client.get(reverse('repartidor_panel')).status_code, 403)

    def test_panel_muestra_solo_sus_pedidos_en_camino(self):
        propio = self._crear_pedido(repartidor=self.repartidor, estado='en_camino')
        ajeno = self._crear_pedido(repartidor=self.otro_rep, estado='en_camino')
        r = self.client.get(reverse('repartidor_panel'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'Pedido #{propio.pk}')
        self.assertNotContains(r, f'Pedido #{ajeno.pk}')

    def test_registrar_entrega_cambia_a_entregado(self):
        pedido = self._crear_pedido(estado='en_camino')
        r = self.client.post(reverse('repartidor_entregar', args=[pedido.pk]))
        self.assertRedirects(r, reverse('repartidor_panel'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'entregado')

    def test_no_puede_entregar_pedido_de_otro_repartidor(self):
        ajeno = self._crear_pedido(repartidor=self.otro_rep, estado='en_camino')
        r = self.client.post(reverse('repartidor_entregar', args=[ajeno.pk]))
        self.assertEqual(r.status_code, 404)
        ajeno.refresh_from_db()
        self.assertEqual(ajeno.estado, 'en_camino')