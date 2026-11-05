from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from menu.models import Category, Product, Sede

from .models import DetallePedido, Pedido

User = get_user_model()


class CocinaBase(TestCase):
    def setUp(self):
        self.cocina = User.objects.create_user('chef', password='x', role='cocina')
        self.ana = User.objects.create_user('ana', password='x', role='cliente')
        self.centro = Sede.objects.create(name='Centro', address='Cra 1')
        self.norte = Sede.objects.create(name='Norte', address='Av 3')
        self.producto = Product.objects.create(
            category=Category.objects.create(name='Platos'),
            name='Hamburguesa', description='Rica', price=Decimal('15000'),
        )
        self.tablero = reverse('cocina_tablero')
        self.tablero_centro = f'{self.tablero}?sede={self.centro.pk}'
        self.client.force_login(self.cocina)

    def crear_pedido(self, sede=None, estado='recibido', observaciones=''):
        pedido = Pedido.objects.create(
            cliente=self.ana, creado_por=self.ana, sede=sede or self.centro,
            tipo_entrega='mostrador', metodo_pago='efectivo',
            subtotal=Decimal('30000'), total=Decimal('30000'),
            estado=estado, observaciones=observaciones,
        )
        DetallePedido.objects.create(
            pedido=pedido, producto=self.producto, cantidad=2,
            precio_unitario=Decimal('15000'), subtotal=Decimal('30000'),
        )
        return pedido

    def avanzar(self, pedido, sede=None, estado_actual=None):
        sede = sede or self.centro
        return self.client.post(
            reverse('cocina_avanzar', args=[pedido.pk]) + f'?sede={sede.pk}',
            {'estado_actual': estado_actual or pedido.estado},
        )


class ReglasDeEstadoTests(CocinaBase):
    def test_flujo_completo(self):
        p = self.crear_pedido()
        self.assertEqual(p.siguiente_estado(), 'en_preparacion')
        p.estado = 'en_preparacion'
        self.assertEqual(p.siguiente_estado(), 'listo')
        p.estado = 'listo'
        self.assertEqual(p.siguiente_estado(), 'entregado')

    def test_estados_finales_no_avanzan(self):
        for estado in ('entregado', 'cancelado'):
            p = self.crear_pedido(estado=estado)
            self.assertIsNone(p.siguiente_estado())
            self.assertFalse(p.puede_avanzar())

    def test_todos_los_estados_del_modelo_tienen_regla(self):
        estados = {valor for valor, _ in Pedido.ESTADOS}
        self.assertEqual(set(Pedido.TRANSICIONES), estados)
        for siguiente in Pedido.TRANSICIONES.values():
            self.assertTrue(siguiente is None or siguiente in estados)


class TableroCocinaTests(CocinaBase):  # HU18
    def test_anonimo_va_al_login(self):
        self.client.logout()
        r = self.client.get(self.tablero)
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)

    def test_otros_roles_reciben_403(self):
        for username, role in [('cli', 'cliente'), ('ope', 'operador'), ('rep', 'repartidor'), ('adm', 'admin')]:
            self.client.force_login(User.objects.create_user(username, password='x', role=role))
            self.assertEqual(self.client.get(self.tablero).status_code, 403, role)

    def test_sin_sede_muestra_selector(self):
        r = self.client.get(self.tablero)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context['sede'])
        self.assertEqual(len(r.context['sedes']), 2)

    def test_recuerda_la_sede_elegida(self):
        self.client.get(self.tablero_centro)
        self.assertEqual(self.client.get(self.tablero).context['sede'], self.centro)

    def test_tres_columnas_con_los_pedidos_en_su_estado(self):
        a = self.crear_pedido(estado='recibido')
        b = self.crear_pedido(estado='en_preparacion')
        c = self.crear_pedido(estado='listo')
        columnas = self.client.get(self.tablero_centro).context['columnas']
        self.assertEqual([col['estado'] for col in columnas], ['recibido', 'en_preparacion', 'listo'])
        self.assertEqual([col['pedidos'] for col in columnas], [[a], [b], [c]])

    def test_solo_pedidos_de_la_sede_y_en_curso(self):
        propio = self.crear_pedido()
        ajeno = self.crear_pedido(sede=self.norte)
        entregado = self.crear_pedido(estado='entregado')
        cancelado = self.crear_pedido(estado='cancelado')
        r = self.client.get(self.tablero_centro)
        self.assertContains(r, f'Pedido #{propio.pk}')
        for otro in (ajeno, entregado, cancelado):
            self.assertNotContains(r, f'Pedido #{otro.pk}')

    def test_la_tarjeta_muestra_productos_cantidades_y_observaciones(self):
        self.crear_pedido(observaciones='sin cebolla')
        r = self.client.get(self.tablero_centro)
        self.assertContains(r, 'Hamburguesa')
        self.assertContains(r, '2×')
        self.assertContains(r, 'sin cebolla')

    def test_el_mas_antiguo_va_primero(self):
        primero = self.crear_pedido()
        segundo = self.crear_pedido()
        columnas = self.client.get(self.tablero_centro).context['columnas']
        self.assertEqual(columnas[0]['pedidos'], [primero, segundo])

    def test_no_hace_una_consulta_por_pedido(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.crear_pedido()
        with CaptureQueriesContext(connection) as con_uno:
            self.client.get(self.tablero_centro)
        for _ in range(4):
            self.crear_pedido()
        with CaptureQueriesContext(connection) as con_cinco:
            self.client.get(self.tablero_centro)
        self.assertEqual(len(con_uno), len(con_cinco))


class AvanzarEstadoTests(CocinaBase):  # HU19
    def test_get_no_cambia_nada(self):
        p = self.crear_pedido()
        r = self.client.get(reverse('cocina_avanzar', args=[p.pk]) + f'?sede={self.centro.pk}')
        self.assertEqual(r.status_code, 405)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'recibido')

    def test_avanza_un_paso_cada_vez(self):
        p = self.crear_pedido()
        for esperado in ('en_preparacion', 'listo', 'entregado'):
            r = self.avanzar(p)
            self.assertRedirects(r, self.tablero, fetch_redirect_response=False)
            p.refresh_from_db()
            self.assertEqual(p.estado, esperado)

    def test_actualiza_updated_at(self):
        p = self.crear_pedido()
        antes = p.updated_at
        self.avanzar(p)
        p.refresh_from_db()
        self.assertGreater(p.updated_at, antes)

    def test_tablero_desactualizado_no_salta_pasos(self):
        p = self.crear_pedido(estado='en_preparacion')
        self.avanzar(p, estado_actual='recibido')   # el tablero aún lo mostraba como recibido
        p.refresh_from_db()
        self.assertEqual(p.estado, 'en_preparacion')

    def test_entregado_y_cancelado_no_se_modifican(self):
        for estado in ('entregado', 'cancelado'):
            p = self.crear_pedido(estado=estado)
            r = self.avanzar(p)
            p.refresh_from_db()
            self.assertEqual(p.estado, estado)
            self.assertContains(self.client.get(r.url), 'no se puede modificar')

    def test_pedido_cancelado_por_el_cliente_mientras_tanto(self):
        p = self.crear_pedido()
        Pedido.objects.filter(pk=p.pk).update(estado='cancelado')  # el cliente canceló tras cargar el tablero
        self.avanzar(p, estado_actual='recibido')
        p.refresh_from_db()
        self.assertEqual(p.estado, 'cancelado')

    def test_no_toca_pedidos_de_otra_sede(self):
        p = self.crear_pedido(sede=self.norte)
        self.assertEqual(self.avanzar(p, sede=self.centro).status_code, 404)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'recibido')

    def test_sin_sede_en_sesion_redirige_al_tablero(self):
        p = self.crear_pedido()
        r = self.client.post(reverse('cocina_avanzar', args=[p.pk]), {'estado_actual': 'recibido'})
        self.assertRedirects(r, self.tablero, fetch_redirect_response=False)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'recibido')

    def test_otros_roles_no_pueden_avanzar(self):
        p = self.crear_pedido()
        for username, role in [('cli', 'cliente'), ('ope', 'operador')]:
            self.client.force_login(User.objects.create_user(username, password='x', role=role))
            self.assertEqual(self.avanzar(p).status_code, 403, role)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'recibido')

    def test_post_sin_csrf_es_rechazado(self):
        from django.test import Client
        p = self.crear_pedido()
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.cocina)
        r = c.post(reverse('cocina_avanzar', args=[p.pk]) + f'?sede={self.centro.pk}', {'estado_actual': 'recibido'})
        self.assertEqual(r.status_code, 403)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'recibido')

    def test_el_tablero_incluye_el_token_csrf_en_el_boton(self):
        self.crear_pedido()
        self.assertContains(self.client.get(self.tablero_centro), 'csrfmiddlewaretoken')
