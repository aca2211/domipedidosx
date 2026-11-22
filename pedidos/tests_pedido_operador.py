from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from menu.models import Category, Product, Sede, SedeProduct
from users.models import Direccion

from .models import Pedido

User = get_user_model()


class OperadorPedidoBase(TestCase):
    def setUp(self):
        self.centro = Sede.objects.create(name='Centro', address='Cra 1')
        self.norte = Sede.objects.create(name='Norte', address='Av 3')
        self.operador = User.objects.create_user('oper', password='x', role='operador', sede=self.centro)
        self.ana = User.objects.create_user('ana', password='x', role='cliente', phone='3001234567')
        self.beto = User.objects.create_user('beto', password='x', role='cliente', phone='3007654321')
        self.casa = Direccion.objects.create(user=self.ana, label='Casa', address='Calle 1 # 2-3')
        self.casa_beto = Direccion.objects.create(user=self.beto, label='Casa', address='Calle 9 # 8-7')
        cat = Category.objects.create(name='Platos')
        self.burger = Product.objects.create(category=cat, name='Burger', description='x', price=Decimal('20000'))
        self.wrap = Product.objects.create(category=cat, name='Wrap', description='x', price=Decimal('15000'))
        SedeProduct.objects.create(sede=self.centro, product=self.burger)
        SedeProduct.objects.create(sede=self.norte, product=self.wrap)
        self.client.force_login(self.operador)

    def elegir_cliente(self, cliente=None):
        self.client.post(reverse('operador_seleccionar_cliente'), {'cliente_id': (cliente or self.ana).id})

    def agregar(self, producto=None, cantidad=1):
        return self.client.post(reverse('operador_agregar'), {
            'product_id': (producto or self.burger).id, 'cantidad': cantidad,
        })

    def confirmar(self, **datos):
        base = {'tipo_entrega': 'mostrador', 'metodo_pago': 'efectivo', 'observaciones': ''}
        base.update(datos)
        return self.client.post(reverse('operador_confirmar'), base)


class AccesoTests(OperadorPedidoBase):
    def test_cliente_recibe_403(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse('operador_armar_pedido')).status_code, 403)
        self.assertEqual(self.client.post(reverse('operador_confirmar')).status_code, 403)

    def test_anonimo_va_al_login(self):
        self.client.logout()
        r = self.client.get(reverse('operador_armar_pedido'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)

    def test_sin_cliente_elegido_vuelve_a_elegir_cliente(self):
        r = self.client.get(reverse('operador_armar_pedido'))
        self.assertRedirects(r, reverse('operador_elegir_cliente'))

    def test_acciones_solo_aceptan_post(self):
        self.assertEqual(self.client.get(reverse('operador_agregar')).status_code, 405)
        self.assertEqual(self.client.get(reverse('operador_confirmar')).status_code, 405)


class SedeDelOperadorTests(OperadorPedidoBase):
    def test_el_operador_con_sede_no_puede_forzar_otra(self):
        r = self.client.get(reverse('operador_elegir_cliente') + f'?sede={self.norte.id}')
        self.assertEqual(r.context['sede'], self.centro)


class ArmarPedidoTests(OperadorPedidoBase):
    def test_muestra_solo_los_productos_de_su_sede(self):
        self.elegir_cliente()
        r = self.client.get(reverse('operador_armar_pedido'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Burger')
        self.assertNotContains(r, 'Wrap')

    def test_agregar_guarda_en_el_carrito_de_la_sesion(self):
        self.elegir_cliente()
        self.agregar(cantidad=2)
        carrito = self.client.session['carrito']
        self.assertEqual(carrito['sede_id'], self.centro.id)
        self.assertEqual(sum(carrito['items'].values()), 2)

    def test_no_se_agrega_un_producto_que_no_esta_en_su_sede(self):
        self.elegir_cliente()
        self.agregar(producto=self.wrap)
        self.assertNotIn('carrito', self.client.session)

    def test_agregar_sin_cliente_elegido_no_hace_nada(self):
        r = self.agregar()
        self.assertRedirects(r, reverse('operador_elegir_cliente'))
        self.assertNotIn('carrito', self.client.session)

    def test_actualizar_cantidad(self):
        self.elegir_cliente()
        self.agregar()
        clave = str(self.burger.id)
        self.client.post(reverse('operador_actualizar', args=[clave]), {'cantidad': 5})
        self.assertEqual(self.client.session['carrito']['items'][clave], 5)

    def test_quitar_producto(self):
        self.elegir_cliente()
        self.agregar()
        self.client.post(reverse('operador_quitar', args=[str(self.burger.id)]))
        self.assertEqual(self.client.session['carrito']['items'], {})


class ConfirmarPedidoOperadorTests(OperadorPedidoBase):
    def test_domicilio_crea_el_pedido_a_nombre_del_cliente(self):
        self.elegir_cliente()
        self.agregar(cantidad=2)
        r = self.confirmar(tipo_entrega='domicilio', direccion=self.casa.id, observaciones='sin sal')
        pedido = Pedido.objects.get()
        self.assertRedirects(r, reverse('operador_pedido_creado', args=[pedido.pk]))
        self.assertEqual(pedido.cliente, self.ana)
        self.assertEqual(pedido.creado_por, self.operador)
        self.assertEqual(pedido.sede, self.centro)
        self.assertEqual(pedido.tipo_entrega, 'domicilio')
        self.assertEqual(pedido.direccion, self.casa)
        self.assertEqual(pedido.total, Decimal('40000'))
        self.assertEqual(pedido.estado, 'recibido')
        self.assertEqual(pedido.detalles.get().cantidad, 2)

    def test_despues_de_confirmar_se_limpia_cliente_y_carrito(self):
        self.elegir_cliente()
        self.agregar()
        self.confirmar()
        self.assertNotIn('operador_cliente_id', self.client.session)
        self.assertNotIn('carrito', self.client.session)

    def test_mostrador_no_necesita_direccion(self):
        self.elegir_cliente()
        self.agregar()
        self.confirmar(tipo_entrega='mostrador')
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.tipo_entrega, 'mostrador')
        self.assertIsNone(pedido.direccion)

    def test_domicilio_sin_direccion_se_rechaza(self):
        self.elegir_cliente()
        self.agregar()
        r = self.confirmar(tipo_entrega='domicilio')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Elige una dirección')
        self.assertEqual(Pedido.objects.count(), 0)

    def test_no_se_acepta_la_direccion_de_otro_cliente(self):
        self.elegir_cliente()
        self.agregar()
        r = self.confirmar(tipo_entrega='domicilio', direccion=self.casa_beto.id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_metodo_de_pago_invalido_se_rechaza(self):
        self.elegir_cliente()
        self.agregar()
        r = self.confirmar(metodo_pago='bitcoin')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_carrito_vacio_no_crea_pedido(self):
        self.elegir_cliente()
        r = self.confirmar()
        self.assertRedirects(r, reverse('operador_armar_pedido'))
        self.assertEqual(Pedido.objects.count(), 0)

    def test_producto_agotado_antes_de_confirmar_no_crea_pedido(self):
        self.elegir_cliente()
        self.agregar()
        SedeProduct.objects.filter(sede=self.centro, product=self.burger).update(is_available=False)
        self.confirmar()
        self.assertEqual(Pedido.objects.count(), 0)


class PedidoCreadoOperadorTests(OperadorPedidoBase):
    def crear(self, sede):
        return Pedido.objects.create(
            cliente=self.ana, creado_por=self.operador, sede=sede, tipo_entrega='mostrador',
            metodo_pago='efectivo', subtotal=1000, total=1000,
        )

    def test_el_operador_ve_los_pedidos_de_su_sede(self):
        pedido = self.crear(self.centro)
        r = self.client.get(reverse('operador_pedido_creado', args=[pedido.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'#{pedido.pk}')

    def test_pedido_de_otra_sede_da_404(self):
        pedido = self.crear(self.norte)
        r = self.client.get(reverse('operador_pedido_creado', args=[pedido.pk]))
        self.assertEqual(r.status_code, 404)
