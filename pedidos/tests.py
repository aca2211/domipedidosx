from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from menu.models import Category, Product, Sede, SedeProduct
from users.models import Direccion

from .models import DetallePedido, Pedido

User = get_user_model()


class BaseTest(TestCase):
    def setUp(self):
        self.cliente = User.objects.create_user('ana', password='x', role='cliente', phone='3001234567')
        self.otro = User.objects.create_user('beto', password='x', role='cliente', phone='3007654321')
        self.cocina = User.objects.create_user('chef', password='x', role='cocina')
        self.sede1 = Sede.objects.create(name='Centro', address='Cra 1')
        self.sede2 = Sede.objects.create(name='Norte', address='Av 3')
        cat = Category.objects.create(name='Comidas')
        self.burger = Product.objects.create(category=cat, name='Burger', description='d', price=Decimal('15000'))
        self.papas = Product.objects.create(category=cat, name='Papas', description='d', price=Decimal('8000'))
        self.soda = Product.objects.create(category=cat, name='Soda', description='d', price=Decimal('4000'))
        SedeProduct.objects.create(sede=self.sede1, product=self.burger)
        SedeProduct.objects.create(sede=self.sede1, product=self.papas)
        SedeProduct.objects.create(sede=self.sede1, product=self.soda, is_available=False)  # agotado en sede1
        SedeProduct.objects.create(sede=self.sede2, product=self.soda)
        SedeProduct.objects.create(sede=self.sede2, product=self.burger)
        self.direccion = Direccion.objects.create(user=self.cliente, label='Casa', address='Calle 5 # 6-7')
        self.client.force_login(self.cliente)

    def agregar(self, producto, sede=None, cantidad=1):
        return self.client.post(reverse('carrito_agregar'), {
            'product_id': producto.id, 'sede_id': (sede or self.sede1).id, 'cantidad': cantidad,
        })

    def carrito_sesion(self):
        return self.client.session.get('carrito', {})

    def confirmar(self, **extra):
        datos = {'direccion': self.direccion.id, 'metodo_pago': 'efectivo', 'observaciones': 'Sin cebolla'}
        datos.update(extra)
        return self.client.post(reverse('pedido_confirmar'), datos)


class CarritoTests(BaseTest):  # HU13
    def test_agrega_producto_disponible(self):
        self.agregar(self.burger, cantidad=2)
        self.assertEqual(self.carrito_sesion()['items'], {str(self.burger.id): 2})
        self.assertEqual(self.carrito_sesion()['sede_id'], self.sede1.id)

    def test_agregar_el_mismo_producto_suma_cantidades(self):
        self.agregar(self.burger)
        self.agregar(self.burger, cantidad=2)
        self.assertEqual(self.carrito_sesion()['items'][str(self.burger.id)], 3)

    def test_no_agrega_producto_agotado_en_la_sede(self):
        self.agregar(self.soda, sede=self.sede1)
        self.assertEqual(self.carrito_sesion().get('items', {}), {})

    def test_producto_disponible_en_otra_sede_no_cuenta(self):
        SedeProduct.objects.filter(sede=self.sede2, product=self.papas).delete()
        self.agregar(self.papas, sede=self.sede2)
        self.assertEqual(self.carrito_sesion().get('items', {}), {})

    def test_agregar_fallido_no_vacia_el_carrito(self):
        self.agregar(self.burger)
        self.agregar(self.soda, sede=self.sede1)  # agotado
        self.assertEqual(self.carrito_sesion()['items'], {str(self.burger.id): 1})

    def test_cambiar_de_sede_vacia_el_carrito(self):
        self.agregar(self.burger, sede=self.sede1)
        self.agregar(self.soda, sede=self.sede2)
        self.assertEqual(self.carrito_sesion()['sede_id'], self.sede2.id)
        self.assertEqual(self.carrito_sesion()['items'], {str(self.soda.id): 1})

    def test_cantidad_minima_es_uno(self):
        self.agregar(self.burger, cantidad=0)
        self.assertEqual(self.carrito_sesion().get('items', {}), {})
        self.agregar(self.burger, cantidad=-3)
        self.assertEqual(self.carrito_sesion().get('items', {}), {})

    def test_actualizar_cantidad(self):
        self.agregar(self.burger)
        self.client.post(reverse('carrito_actualizar', args=[self.burger.id]), {'cantidad': 4})
        self.assertEqual(self.carrito_sesion()['items'][str(self.burger.id)], 4)

    def test_actualizar_a_cero_se_rechaza(self):
        self.agregar(self.burger)
        self.client.post(reverse('carrito_actualizar', args=[self.burger.id]), {'cantidad': 0})
        self.assertEqual(self.carrito_sesion()['items'][str(self.burger.id)], 1)

    def test_quitar_producto(self):
        self.agregar(self.burger)
        self.agregar(self.papas)
        self.client.post(reverse('carrito_quitar', args=[self.burger.id]))
        self.assertEqual(self.carrito_sesion()['items'], {str(self.papas.id): 1})

    def test_subtotal_y_total(self):
        self.agregar(self.burger, cantidad=2)
        self.agregar(self.papas)
        r = self.client.get(reverse('carrito_ver'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['subtotal'], Decimal('38000'))
        self.assertEqual(r.context['total'], Decimal('38000'))

    def test_carrito_marca_producto_que_se_agoto(self):
        self.agregar(self.burger)
        SedeProduct.objects.filter(sede=self.sede1, product=self.burger).update(is_available=False)
        r = self.client.get(reverse('carrito_ver'))
        self.assertTrue(r.context['hay_agotados'])

    def test_agregar_solo_acepta_post(self):
        self.assertEqual(self.client.get(reverse('carrito_agregar')).status_code, 405)

    def test_rol_incorrecto_recibe_403(self):
        self.client.force_login(self.cocina)
        self.assertEqual(self.client.get(reverse('carrito_ver')).status_code, 403)
        self.assertEqual(self.agregar(self.burger).status_code, 403)

    def test_anonimo_va_al_login(self):
        self.client.logout()
        r = self.client.get(reverse('carrito_ver'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)

    def test_menu_con_sede_muestra_boton_agregar(self):
        r = self.client.get(reverse('menu_list') + f'?sede={self.sede1.id}')
        self.assertContains(r, reverse('carrito_agregar'))

    def test_next_externo_no_redirige_fuera_del_sitio(self):
        r = self.client.post(reverse('carrito_agregar'), {
            'product_id': self.burger.id, 'sede_id': self.sede1.id, 'cantidad': 1,
            'next': 'https://sitio-malicioso.com/',
        })
        self.assertRedirects(r, reverse('carrito_ver'))


class ConfirmarPedidoTests(BaseTest):  # HU14
    def test_confirmar_crea_pedido_y_detalles(self):
        self.agregar(self.burger, cantidad=2)
        self.agregar(self.papas)
        r = self.confirmar()
        pedido = Pedido.objects.get()
        self.assertRedirects(r, reverse('pedido_creado', args=[pedido.pk]))
        self.assertEqual(pedido.estado, 'recibido')
        self.assertEqual(pedido.cliente, self.cliente)
        self.assertEqual(pedido.creado_por, self.cliente)
        self.assertEqual(pedido.sede, self.sede1)
        self.assertEqual(pedido.direccion, self.direccion)
        self.assertEqual(pedido.metodo_pago, 'efectivo')
        self.assertEqual(pedido.observaciones, 'Sin cebolla')
        self.assertEqual(pedido.subtotal, Decimal('38000'))
        self.assertEqual(pedido.costo_domicilio, Decimal('0'))
        self.assertEqual(pedido.total, Decimal('38000'))
        self.assertEqual(pedido.detalles.count(), 2)

    def test_precio_queda_congelado(self):
        self.agregar(self.burger, cantidad=2)
        self.confirmar()
        self.burger.price = Decimal('99999')
        self.burger.save()
        detalle = DetallePedido.objects.get()
        pedido = Pedido.objects.get()
        self.assertEqual(detalle.precio_unitario, Decimal('15000'))
        self.assertEqual(detalle.subtotal, Decimal('30000'))
        self.assertEqual(pedido.total, Decimal('30000'))

    def test_producto_agotado_entre_carrito_y_confirmacion_bloquea(self):
        self.agregar(self.burger)
        SedeProduct.objects.filter(sede=self.sede1, product=self.burger).update(is_available=False)
        r = self.confirmar()
        self.assertRedirects(r, reverse('carrito_ver'))
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(self.carrito_sesion()['items'], {str(self.burger.id): 1})

    def test_sin_direcciones_no_crea_pedido(self):
        self.cliente.direcciones.all().delete()
        self.agregar(self.burger)
        self.assertEqual(self.client.get(reverse('pedido_confirmar')).status_code, 302)
        self.assertEqual(self.confirmar().status_code, 302)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_no_acepta_direccion_de_otro_cliente(self):
        ajena = Direccion.objects.create(user=self.otro, label='Casa', address='Otra calle 1')
        self.agregar(self.burger)
        r = self.confirmar(direccion=ajena.id)
        self.assertEqual(r.status_code, 200)  # formulario inválido
        self.assertEqual(Pedido.objects.count(), 0)

    def test_carrito_vacio_no_crea_pedido(self):
        r = self.client.get(reverse('pedido_confirmar'))
        self.assertRedirects(r, reverse('menu_list'))
        self.assertEqual(self.confirmar().status_code, 302)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_el_carrito_se_vacia_tras_confirmar(self):
        self.agregar(self.burger)
        self.confirmar()
        self.assertEqual(self.carrito_sesion().get('items', {}), {})

    def test_metodo_de_pago_invalido_no_crea_pedido(self):
        self.agregar(self.burger)
        r = self.confirmar(metodo_pago='bitcoin')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_pagina_de_pedido_creado_solo_para_el_dueno(self):
        self.agregar(self.burger)
        self.confirmar()
        pedido = Pedido.objects.get()
        self.assertEqual(self.client.get(reverse('pedido_creado', args=[pedido.pk])).status_code, 200)
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(reverse('pedido_creado', args=[pedido.pk])).status_code, 404)

    def test_rol_incorrecto_recibe_403_al_confirmar(self):
        self.client.force_login(self.cocina)
        self.assertEqual(self.client.get(reverse('pedido_confirmar')).status_code, 403)