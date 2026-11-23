from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from menu.models import Category, Product, Sede

from .models import DetallePedido, Pedido

User = get_user_model()


class HistorialBase(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', password='x', role='cliente')
        self.beto = User.objects.create_user('beto', password='x', role='cliente')
        self.cocina = User.objects.create_user('chef', password='x', role='cocina')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        self.url = reverse('mis_pedidos')
        self.client.force_login(self.ana)

    def crear_pedido(self, cliente=None, estado='recibido', total='15000', hace_horas=0):
        cliente = cliente or self.ana
        pedido = Pedido.objects.create(
            cliente=cliente, creado_por=cliente, sede=self.sede,
            tipo_entrega='mostrador', metodo_pago='efectivo',
            subtotal=Decimal(total), total=Decimal(total), estado=estado,
        )
        Pedido.objects.filter(pk=pedido.pk).update(created_at=timezone.now() - timedelta(hours=hace_horas))
        return pedido


class HistorialPedidosTests(HistorialBase): 
    def test_lista_solo_los_pedidos_propios(self):
        mio = self.crear_pedido()
        ajeno = self.crear_pedido(cliente=self.beto)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(r.context['pedidos']), [mio])
        self.assertNotIn(ajeno, r.context['pedidos'])

    def test_del_mas_reciente_al_mas_antiguo(self):
        viejo = self.crear_pedido(hace_horas=48)
        nuevo = self.crear_pedido(hace_horas=1)
        medio = self.crear_pedido(hace_horas=24)
        r = self.client.get(self.url)
        self.assertEqual(list(r.context['pedidos']), [nuevo, medio, viejo])

    def test_muestra_estado_y_total(self):
        self.crear_pedido(estado='en_preparacion', total='38000')
        r = self.client.get(self.url)
        self.assertContains(r, 'En preparacion')
        self.assertContains(r, '$38000')

    def test_incluye_los_pedidos_cancelados(self):
        cancelado = self.crear_pedido(estado='cancelado')
        r = self.client.get(self.url)
        self.assertIn(cancelado, r.context['pedidos'])
        self.assertContains(r, 'Cancelado')

    def test_cuenta_los_productos_de_cada_pedido(self):
        pedido = self.crear_pedido()
        cat = Category.objects.create(name='Comidas')
        for nombre in ('Burger', 'Papas'):
            prod = Product.objects.create(category=cat, name=nombre, description='d', price=Decimal('5000'))
            DetallePedido.objects.create(pedido=pedido, producto=prod, cantidad=1,
                                         precio_unitario=Decimal('5000'), subtotal=Decimal('5000'))
        r = self.client.get(self.url)
        self.assertEqual(r.context['pedidos'][0].num_productos, 2)
        self.assertContains(r, '2 productos')

    def test_cada_pedido_enlaza_a_su_pantalla(self):
        pedido = self.crear_pedido()
        r = self.client.get(self.url)
        self.assertContains(r, reverse('pedido_creado', args=[pedido.pk]))

    def test_sin_pedidos_muestra_mensaje_vacio(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'Todavía no has hecho pedidos')

    def test_rol_incorrecto_recibe_403(self):
        self.client.force_login(self.cocina)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonimo_va_al_login(self):
        self.client.logout()
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)


class EnlacesHistorialTests(HistorialBase): 
    def test_el_inicio_enlaza_al_historial_para_clientes(self):
        r = self.client.get(reverse('home'))
        self.assertContains(r, reverse('mis_pedidos'))

    def test_otros_roles_no_ven_el_enlace(self):
        self.client.force_login(self.cocina)
        r = self.client.get(reverse('home'))
        self.assertNotContains(r, reverse('mis_pedidos'))

    def test_la_pantalla_del_pedido_enlaza_al_historial(self):
        pedido = self.crear_pedido()
        r = self.client.get(reverse('pedido_creado', args=[pedido.pk]))
        self.assertContains(r, reverse('mis_pedidos'))