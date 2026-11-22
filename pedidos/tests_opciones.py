from decimal import Decimal

from django.urls import reverse

from menu.models import ProductOption

from .models import DetallePedido
from .tests import BaseTest


class OpcionesBaseTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.normal = ProductOption.objects.create(product=self.burger, kind='size', name='Normal')
        self.grande = ProductOption.objects.create(product=self.burger, kind='size', name='Grande', extra_price=Decimal('4000'))
        self.tocineta = ProductOption.objects.create(product=self.burger, kind='addon', name='Tocineta', extra_price=Decimal('3000'))
        self.queso = ProductOption.objects.create(product=self.burger, kind='addon', name='Queso', extra_price=Decimal('2000'))
        self.cebolla = ProductOption.objects.create(product=self.burger, kind='exclusion', name='Cebolla')

    def agregar_con(self, tamano=None, opciones=(), cantidad=1, producto=None):
        datos = {'product_id': (producto or self.burger).id, 'sede_id': self.sede1.id, 'cantidad': cantidad}
        if tamano is not None:
            datos['tamano'] = tamano.id
        if opciones:
            datos['opciones'] = [o.id for o in opciones]
        return self.client.post(reverse('carrito_agregar'), datos, follow=True)

    def lineas(self):
        return self.client.get(reverse('carrito_ver')).context['lineas']


class AgregarConOpcionesTests(OpcionesBaseTest):  # HU10
    def test_el_precio_suma_los_recargos(self):
        self.agregar_con(self.grande, [self.tocineta, self.cebolla], cantidad=2)
        (linea,) = self.lineas()
        self.assertEqual(linea['precio'], Decimal('22000'))   # 15000 + 4000 + 3000
        self.assertEqual(linea['subtotal'], Decimal('44000'))
        self.assertEqual({o['name'] for o in linea['opciones']}, {'Grande', 'Tocineta', 'Cebolla'})

    def test_misma_configuracion_suma_cantidad(self):
        self.agregar_con(self.normal, [self.queso])
        self.agregar_con(self.normal, [self.queso], cantidad=2)
        (linea,) = self.lineas()
        self.assertEqual(linea['cantidad'], 3)

    def test_distinta_configuracion_es_otra_linea(self):
        self.agregar_con(self.normal)
        self.agregar_con(self.grande)
        self.agregar_con(self.grande, [self.queso])
        self.assertEqual(len(self.lineas()), 3)

    def test_el_orden_de_las_opciones_no_crea_lineas_distintas(self):
        self.agregar_con(self.normal, [self.queso, self.tocineta])
        self.agregar_con(self.normal, [self.tocineta, self.queso])
        self.assertEqual(len(self.lineas()), 1)

    def test_con_tamanos_el_tamano_es_obligatorio(self):
        r = self.agregar_con(None, [self.queso])
        self.assertContains(r, 'Elige un tamaño')
        self.assertEqual(self.carrito_sesion().get('items', {}), {})

    def test_solo_un_tamano(self):
        r = self.client.post(reverse('carrito_agregar'), {
            'product_id': self.burger.id, 'sede_id': self.sede1.id, 'cantidad': 1,
            'opciones': [self.normal.id, self.grande.id],
        }, follow=True)
        self.assertContains(r, 'Elige un solo tamaño')
        self.assertEqual(self.carrito_sesion().get('items', {}), {})

    def test_opcion_de_otro_producto_se_rechaza(self):
        ajena = ProductOption.objects.create(product=self.papas, kind='addon', name='Salsa')
        r = self.agregar_con(self.normal, [ajena])
        self.assertContains(r, 'no está disponible')
        self.assertEqual(self.carrito_sesion().get('items', {}), {})

    def test_opcion_inactiva_se_rechaza(self):
        self.queso.is_active = False
        self.queso.save()
        r = self.agregar_con(self.normal, [self.queso])
        self.assertContains(r, 'no está disponible')

    def test_producto_sin_opciones_sigue_igual(self):
        self.agregar_con(producto=self.papas)
        self.assertEqual(self.carrito_sesion()['items'], {str(self.papas.id): 1})

    def test_ids_basura_no_rompen(self):
        r = self.client.post(reverse('carrito_agregar'), {
            'product_id': self.papas.id, 'sede_id': self.sede1.id, 'cantidad': 1, 'opciones': ['abc', ''],
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.carrito_sesion()['items'], {str(self.papas.id): 1})


class EditarCarritoConOpcionesTests(OpcionesBaseTest):
    def test_actualizar_y_quitar_una_linea_con_opciones(self):
        self.agregar_con(self.normal)
        self.agregar_con(self.grande, [self.queso])
        clave = next(l['clave'] for l in self.lineas() if l['opciones_invalidas'] is False and len(l['opciones']) == 2)
        self.client.post(reverse('carrito_actualizar', args=[clave]), {'cantidad': 5})
        self.assertEqual(self.carrito_sesion()['items'][clave], 5)
        self.client.post(reverse('carrito_quitar', args=[clave]))
        self.assertNotIn(clave, self.carrito_sesion()['items'])
        self.assertEqual(len(self.lineas()), 1)

    def test_clave_inexistente_no_rompe(self):
        self.agregar_con(self.normal)
        r = self.client.post(reverse('carrito_actualizar', args=['999-1-2']), {'cantidad': 2}, follow=True)
        self.assertContains(r, 'no está en tu carrito')

    def test_opcion_desactivada_despues_bloquea_la_confirmacion(self):
        self.agregar_con(self.normal, [self.queso])
        self.queso.is_active = False
        self.queso.save()
        r = self.client.get(reverse('carrito_ver'))
        self.assertTrue(r.context['hay_opciones_invalidas'])
        self.assertContains(r, 'Una opción ya no está disponible')
        r = self.confirmar()
        self.assertRedirects(r, reverse('carrito_ver'))
        self.assertEqual(DetallePedido.objects.count(), 0)


class PedidoGuardaOpcionesTests(OpcionesBaseTest):
    def test_el_pedido_congela_opciones_y_precio(self):
        self.agregar_con(self.grande, [self.tocineta, self.cebolla])
        self.confirmar()
        detalle = DetallePedido.objects.get()
        self.assertEqual(detalle.precio_unitario, Decimal('22000'))
        self.assertEqual(
            sorted((o['kind'], o['name'], o['extra']) for o in detalle.opciones),
            [('addon', 'Tocineta', '3000.00'), ('exclusion', 'Cebolla', '0.00'), ('size', 'Grande', '4000.00')],
        )
        # Si el menú cambia después, el pedido no cambia
        self.grande.extra_price = Decimal('9999')
        self.grande.name = 'Gigante'
        self.grande.save()
        self.tocineta.delete()
        detalle.refresh_from_db()
        self.assertEqual(detalle.precio_unitario, Decimal('22000'))
        self.assertIn('Grande', [o['name'] for o in detalle.opciones])
        self.assertIn('Tocineta', [o['name'] for o in detalle.opciones])

    def test_opciones_lista_marca_los_recargos(self):
        self.agregar_con(self.normal, [self.queso, self.cebolla])
        self.confirmar()
        lista = {o['name']: o['con_recargo'] for o in DetallePedido.objects.get().opciones_lista}
        self.assertEqual(lista, {'Normal': False, 'Queso': True, 'Cebolla': False})

    def test_detalle_sin_opciones_tiene_lista_vacia(self):
        self.agregar_con(producto=self.papas)
        self.confirmar()
        self.assertEqual(DetallePedido.objects.get().opciones_lista, [])

    def test_el_cliente_ve_las_opciones_en_su_pedido_y_en_la_confirmacion(self):
        self.agregar_con(self.grande, [self.queso, self.cebolla])
        self.assertContains(self.client.get(reverse('pedido_confirmar')), 'Sin Cebolla')
        pedido = self.confirmar().url
        r = self.client.get(pedido)
        self.assertContains(r, 'Sin Cebolla')
        self.assertContains(r, 'Tamaño: Grande')
        self.assertContains(r, '+ Queso')

    def test_la_cocina_ve_las_exclusiones(self):
        self.agregar_con(self.normal, [self.cebolla])
        self.confirmar()
        self.client.force_login(self.cocina)
        r = self.client.get(reverse('cocina_tablero') + f'?sede={self.sede1.id}')
        self.assertContains(r, 'Sin Cebolla')
