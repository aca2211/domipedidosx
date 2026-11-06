from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from menu.models import Sede

from .models import Pedido

User = get_user_model()


class SeguimientoPedidoTests(TestCase):  # HU20
    def setUp(self):
        self.ana = User.objects.create_user('ana', password='x', role='cliente')
        self.beto = User.objects.create_user('beto', password='x', role='cliente')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        self.client.force_login(self.ana)

    def crear_pedido(self, estado='recibido', cliente=None):
        cliente = cliente or self.ana
        return Pedido.objects.create(
            cliente=cliente, creado_por=cliente, sede=self.sede,
            tipo_entrega='mostrador', metodo_pago='efectivo',
            subtotal=Decimal('15000'), total=Decimal('15000'), estado=estado,
        )

    def ver(self, pedido):
        return self.client.get(reverse('pedido_creado', args=[pedido.pk]))

    def test_solo_el_dueno_lo_ve(self):
        p = self.crear_pedido(cliente=self.beto)
        self.assertEqual(self.ver(p).status_code, 404)

    def test_muestra_los_cuatro_pasos_con_el_actual_marcado(self):
        p = self.crear_pedido(estado='en_preparacion')
        r = self.ver(p)
        pasos = r.context['pasos']
        self.assertEqual(len(pasos), 4)
        self.assertEqual([x['hecho'] for x in pasos], [True, False, False, False])
        self.assertEqual([x['actual'] for x in pasos], [False, True, False, False])
        for nombre in ('Recibido', 'En preparacion', 'Listo', 'Entregado'):
            self.assertContains(r, nombre)

    def test_cada_estado_marca_el_paso_correcto(self):
        esperado = {'recibido': 0, 'en_preparacion': 1, 'listo': 2, 'entregado': 3}
        for estado, indice in esperado.items():
            pasos = self.ver(self.crear_pedido(estado=estado)).context['pasos']
            self.assertEqual([i for i, x in enumerate(pasos) if x['actual']], [indice], estado)
            self.assertEqual(sum(x['hecho'] for x in pasos), indice, estado)

    def test_se_refresca_solo_mientras_esta_en_curso(self):
        for estado in ('recibido', 'en_preparacion', 'listo'):
            self.assertContains(self.ver(self.crear_pedido(estado=estado)), 'window.location.reload', msg_prefix=estado)
        for estado in ('entregado', 'cancelado'):
            self.assertNotContains(self.ver(self.crear_pedido(estado=estado)), 'window.location.reload', msg_prefix=estado)

    def test_cancelado_no_muestra_indicador(self):
        r = self.ver(self.crear_pedido(estado='cancelado'))
        self.assertContains(r, 'Pedido cancelado')
        self.assertNotContains(r, 'rounded-circle')

    def test_el_cliente_ve_el_cambio_que_hace_la_cocina(self):
        cocina = User.objects.create_user('chef', password='x', role='cocina')
        p = self.crear_pedido()
        self.assertEqual([x['actual'] for x in self.ver(p).context['pasos']], [True, False, False, False])
        self.client.force_login(cocina)
        self.client.post(reverse('cocina_avanzar', args=[p.pk]) + f'?sede={self.sede.pk}', {'estado_actual': 'recibido'})
        self.client.force_login(self.ana)
        self.assertEqual([x['actual'] for x in self.ver(p).context['pasos']], [False, True, False, False])
