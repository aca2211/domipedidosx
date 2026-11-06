from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from menu.models import Sede

from .models import Pedido
from .services import CancelacionError, cancelar_pedido

User = get_user_model()


class CancelarPedidoServicioTests(TestCase):  # HU16 · lógica
    def setUp(self):
        self.ana = User.objects.create_user('ana', password='x', role='cliente')
        self.beto = User.objects.create_user('beto', password='x', role='cliente')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')

    def crear_pedido(self, cliente=None, estado='recibido'):
        return Pedido.objects.create(
            cliente=cliente or self.ana, creado_por=cliente or self.ana, sede=self.sede,
            tipo_entrega='mostrador', metodo_pago='efectivo',
            subtotal=Decimal('15000'), total=Decimal('15000'), estado=estado,
        )

    def test_cancela_un_pedido_recibido(self):
        pedido = self.crear_pedido()
        cancelado = cancelar_pedido(pedido.pk, self.ana)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'cancelado')
        self.assertEqual(cancelado.estado, 'cancelado')

    def test_el_pedido_cancelado_no_se_borra(self):
        pedido = self.crear_pedido()
        cancelar_pedido(pedido.pk, self.ana)
        self.assertEqual(Pedido.objects.count(), 1)

    def test_no_cancela_si_ya_paso_de_recibido(self):
        for estado in ('en_preparacion', 'listo', 'entregado', 'cancelado'):
            with self.subTest(estado=estado):
                pedido = self.crear_pedido(estado=estado)
                with self.assertRaises(CancelacionError):
                    cancelar_pedido(pedido.pk, self.ana)
                pedido.refresh_from_db()
                self.assertEqual(pedido.estado, estado)  # no cambia nada

    def test_mensaje_claro_cuando_esta_en_preparacion(self):
        pedido = self.crear_pedido(estado='en_preparacion')
        with self.assertRaises(CancelacionError) as ctx:
            cancelar_pedido(pedido.pk, self.ana)
        self.assertIn('en preparación', str(ctx.exception))

    def test_no_cancela_el_pedido_de_otro_cliente(self):
        pedido = self.crear_pedido(cliente=self.beto)
        with self.assertRaises(Pedido.DoesNotExist):
            cancelar_pedido(pedido.pk, self.ana)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'recibido')

    def test_pedido_inexistente(self):
        with self.assertRaises(Pedido.DoesNotExist):
            cancelar_pedido(9999, self.ana)




class CancelarPedidoVistaTests(TestCase):  # HU16 · pantalla
    def setUp(self):
        self.ana = User.objects.create_user('ana', password='x', role='cliente')
        self.beto = User.objects.create_user('beto', password='x', role='cliente')
        self.cocina = User.objects.create_user('chef', password='x', role='cocina')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        self.client.force_login(self.ana)

    def crear_pedido(self, cliente=None, estado='recibido'):
        cliente = cliente or self.ana
        return Pedido.objects.create(
            cliente=cliente, creado_por=cliente, sede=self.sede,
            tipo_entrega='mostrador', metodo_pago='efectivo',
            subtotal=Decimal('15000'), total=Decimal('15000'), estado=estado,
        )

    def cancelar(self, pedido, **kwargs):
        return self.client.post(reverse('pedido_cancelar', args=[pedido.pk]), **kwargs)

    def test_cancela_su_pedido_recibido(self):
        pedido = self.crear_pedido()
        r = self.cancelar(pedido)
        self.assertRedirects(r, reverse('pedido_creado', args=[pedido.pk]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'cancelado')

    def test_en_preparacion_muestra_mensaje_y_no_cambia(self):
        pedido = self.crear_pedido(estado='en_preparacion')
        r = self.cancelar(pedido, follow=True)
        self.assertContains(r, 'ya está en preparación')
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'en_preparacion')

    def test_entregado_y_cancelado_no_cambian(self):
        for estado in ('entregado', 'cancelado'):
            with self.subTest(estado=estado):
                pedido = self.crear_pedido(estado=estado)
                self.cancelar(pedido)
                pedido.refresh_from_db()
                self.assertEqual(pedido.estado, estado)

    def test_no_puede_cancelar_el_pedido_de_otro_cliente(self):
        pedido = self.crear_pedido(cliente=self.beto)
        self.assertEqual(self.cancelar(pedido).status_code, 404)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'recibido')

    def test_cancelar_solo_acepta_post(self):
        pedido = self.crear_pedido()
        r = self.client.get(reverse('pedido_cancelar', args=[pedido.pk]))
        self.assertEqual(r.status_code, 405)

    def test_rol_incorrecto_recibe_403(self):
        pedido = self.crear_pedido()
        self.client.force_login(self.cocina)
        self.assertEqual(self.cancelar(pedido).status_code, 403)

    def test_anonimo_va_al_login(self):
        pedido = self.crear_pedido()
        self.client.logout()
        r = self.cancelar(pedido)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)

    def test_el_boton_solo_aparece_si_esta_recibido(self):
        recibido = self.crear_pedido()
        preparando = self.crear_pedido(estado='en_preparacion')
        r = self.client.get(reverse('pedido_creado', args=[recibido.pk]))
        self.assertContains(r, reverse('pedido_cancelar', args=[recibido.pk]))
        r = self.client.get(reverse('pedido_creado', args=[preparando.pk]))
        self.assertNotContains(r, reverse('pedido_cancelar', args=[preparando.pk]))

    def test_la_pantalla_muestra_que_esta_cancelado(self):
        pedido = self.crear_pedido(estado='cancelado')
        r = self.client.get(reverse('pedido_creado', args=[pedido.pk]))
        self.assertContains(r, 'Pedido cancelado')