from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from menu.models import Category, Product, ProductOption, Sede, SedeProduct

from .cart import clave_linea
from .models import DetallePedido, Pedido

User = get_user_model()


class RepetirBase(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', password='x', role='cliente')
        self.beto = User.objects.create_user('beto', password='x', role='cliente')
        self.cocina = User.objects.create_user('chef', password='x', role='cocina')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        cat = Category.objects.create(name='Platos')
        self.burger = Product.objects.create(category=cat, name='Burger', description='x', price=Decimal('20000'))
        self.soda = Product.objects.create(category=cat, name='Soda', description='x', price=Decimal('4000'))
        SedeProduct.objects.create(sede=self.sede, product=self.burger)
        SedeProduct.objects.create(sede=self.sede, product=self.soda)
        self.queso = ProductOption.objects.create(
            product=self.burger, kind='addon', name='Queso', extra_price=Decimal('2000'))
        self.client.force_login(self.ana)

    def crear_pedido(self, cliente=None, lineas=None):
        """lineas: lista de (producto, cantidad, opciones guardadas). Por defecto 2 Burger con Queso."""
        cliente = cliente or self.ana
        pedido = Pedido.objects.create(
            cliente=cliente, creado_por=cliente, sede=self.sede, tipo_entrega='mostrador',
            metodo_pago='efectivo', subtotal=Decimal('1000'), total=Decimal('1000'), estado='entregado',
        )
        if lineas is None:
            lineas = [(self.burger, 2, [{'kind': 'addon', 'name': 'Queso', 'extra': '2000.00'}])]
        for producto, cantidad, opciones in lineas:
            DetallePedido.objects.create(
                pedido=pedido, producto=producto, cantidad=cantidad,
                precio_unitario=producto.price, subtotal=producto.price * cantidad, opciones=opciones,
            )
        return pedido

    def repetir(self, pedido):
        return self.client.post(reverse('pedido_repetir', args=[pedido.pk]))

    def mensajes(self, respuesta):
        return [m.message for m in get_messages(respuesta.wsgi_request)]

    def items(self):
        return self.client.session['carrito']['items']


class RepetirPedidoTests(RepetirBase):  # HU17
    def test_copia_productos_cantidades_y_opciones_al_carrito(self):
        r = self.repetir(self.crear_pedido())
        self.assertRedirects(r, reverse('carrito_ver'))
        self.assertEqual(self.items(), {clave_linea(self.burger.id, [self.queso.id]): 2})
        self.assertEqual(self.client.session['carrito']['sede_id'], self.sede.id)

    def test_repite_un_producto_con_tamano(self):
        grande = ProductOption.objects.create(
            product=self.burger, kind='size', name='Grande', extra_price=Decimal('4000'))
        pedido = self.crear_pedido(lineas=[(self.burger, 1, [
            {'kind': 'size', 'name': 'Grande', 'extra': '4000.00'},
            {'kind': 'addon', 'name': 'Queso', 'extra': '2000.00'},
        ])])
        self.repetir(pedido)
        self.assertEqual(self.items(), {clave_linea(self.burger.id, [grande.id, self.queso.id]): 1})

    def test_usa_el_precio_actual(self):
        pedido = self.crear_pedido()
        self.burger.price = Decimal('25000')
        self.burger.save()
        self.repetir(pedido)
        r = self.client.get(reverse('carrito_ver'))
        self.assertEqual(r.context['subtotal'], Decimal('54000'))  # (25000 + 2000) x 2

    def test_reemplaza_el_carrito_anterior(self):
        self.client.post(reverse('carrito_agregar'), {
            'product_id': self.soda.id, 'sede_id': self.sede.id, 'cantidad': 1,
        })
        r = self.repetir(self.crear_pedido())
        self.assertEqual(self.items(), {clave_linea(self.burger.id, [self.queso.id]): 2})
        self.assertTrue(any('reemplazó' in m for m in self.mensajes(r)))

    def test_un_producto_agotado_se_omite_y_el_resto_entra(self):
        pedido = self.crear_pedido(lineas=[(self.burger, 1, []), (self.soda, 3, [])])
        SedeProduct.objects.filter(sede=self.sede, product=self.soda).update(is_available=False)
        r = self.repetir(pedido)
        self.assertRedirects(r, reverse('carrito_ver'))
        self.assertEqual(self.items(), {str(self.burger.id): 1})
        self.assertTrue(any('Soda' in m for m in self.mensajes(r)))

    def test_si_una_opcion_ya_no_existe_la_linea_se_omite_y_se_conserva_el_carrito(self):
        self.client.post(reverse('carrito_agregar'), {
            'product_id': self.soda.id, 'sede_id': self.sede.id, 'cantidad': 2,
        })
        pedido = self.crear_pedido()
        ProductOption.objects.filter(pk=self.queso.pk).update(is_active=False)
        r = self.repetir(pedido)
        self.assertRedirects(r, reverse('mis_pedidos'))
        self.assertEqual(self.items(), {str(self.soda.id): 2})   # el carrito previo sigue igual
        self.assertTrue(any('Queso' in m for m in self.mensajes(r)))

    def test_sede_inactiva_no_agrega_nada(self):
        pedido = self.crear_pedido()
        self.sede.is_active = False
        self.sede.save()
        r = self.repetir(pedido)
        self.assertRedirects(r, reverse('mis_pedidos'))
        self.assertNotIn('carrito', self.client.session)

    def test_no_se_puede_repetir_el_pedido_de_otro_cliente(self):
        ajeno = self.crear_pedido(cliente=self.beto)
        self.assertEqual(self.repetir(ajeno).status_code, 404)
        self.assertNotIn('carrito', self.client.session)

    def test_solo_acepta_post(self):
        pedido = self.crear_pedido()
        r = self.client.get(reverse('pedido_repetir', args=[pedido.pk]))
        self.assertEqual(r.status_code, 405)

    def test_otros_roles_reciben_403(self):
        pedido = self.crear_pedido()
        self.client.force_login(self.cocina)
        self.assertEqual(self.repetir(pedido).status_code, 403)

    def test_anonimo_va_al_login(self):
        pedido = self.crear_pedido()
        self.client.logout()
        r = self.repetir(pedido)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)

    def test_el_historial_muestra_el_boton_repetir(self):
        pedido = self.crear_pedido()
        r = self.client.get(reverse('mis_pedidos'))
        self.assertContains(r, reverse('pedido_repetir', args=[pedido.pk]))
        self.assertContains(r, 'Repetir pedido')
