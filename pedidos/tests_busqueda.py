from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from menu.models import Sede

from .models import Pedido

User = get_user_model()


class BusquedaBase(TestCase):  # HU33
    def setUp(self):
        self.centro = Sede.objects.create(name='Centro', address='Cra 1')
        self.norte = Sede.objects.create(name='Norte', address='Av 3')
        self.admin = User.objects.create_user('admin1', password='x', role='admin')
        self.ana = User.objects.create_user(
            'ana', password='x', role='cliente', first_name='Ana', last_name='Ruiz',
            email='ana@correo.com', phone='3001112233')
        self.luis = User.objects.create_user(
            'luis', password='x', role='cliente', first_name='Luis', last_name='Mora',
            email='luis@correo.com', phone='3109998877')
        self.client.force_login(self.admin)

    def crear_pedido(self, cliente=None, sede=None, estado='recibido', dias_atras=0):
        cliente = cliente or self.ana
        pedido = Pedido.objects.create(
            cliente=cliente, creado_por=cliente, sede=sede or self.centro,
            metodo_pago='efectivo', subtotal='38000', total='38000', estado=estado,
        )
        if dias_atras:  # auto_now_add impide fijar la fecha al crear
            Pedido.objects.filter(pk=pedido.pk).update(created_at=timezone.now() - timedelta(days=dias_atras))
        return pedido

    def ids(self, respuesta):
        return [p.pk for p in respuesta.context['pagina']]


class BuscarPedidosTests(BusquedaBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('buscar_pedidos')

    # --- acceso ---
    def test_cliente_recibe_403(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_operador_recibe_403(self):
        oper = User.objects.create_user('oper', password='x', role='operador', sede=self.centro)
        self.client.force_login(oper)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonimo_no_entra(self):
        self.client.logout()
        self.assertIn(self.client.get(self.url).status_code, (302, 403))

    # --- filtros ---
    def test_sin_filtros_muestra_todos_los_pedidos_de_todas_las_sedes(self):
        a = self.crear_pedido(sede=self.centro)
        b = self.crear_pedido(sede=self.norte)
        self.assertCountEqual(self.ids(self.client.get(self.url)), [a.pk, b.pk])

    def test_filtra_por_sede(self):
        self.crear_pedido(sede=self.centro)
        b = self.crear_pedido(sede=self.norte)
        self.assertEqual(self.ids(self.client.get(self.url, {'sede': self.norte.id})), [b.pk])

    def test_filtra_por_estado(self):
        self.crear_pedido(estado='recibido')
        b = self.crear_pedido(estado='entregado')
        self.assertEqual(self.ids(self.client.get(self.url, {'estado': 'entregado'})), [b.pk])

    def test_estado_inventado_se_ignora(self):
        a = self.crear_pedido()
        self.assertEqual(self.ids(self.client.get(self.url, {'estado': 'xyz'})), [a.pk])

    def test_filtra_por_rango_de_fechas(self):
        hoy = timezone.localdate()
        viejo = self.crear_pedido(dias_atras=10)
        medio = self.crear_pedido(dias_atras=5)
        reciente = self.crear_pedido()
        desde = (hoy - timedelta(days=7)).isoformat()
        hasta = (hoy - timedelta(days=7)).isoformat()
        self.assertCountEqual(self.ids(self.client.get(self.url, {'desde': desde})), [medio.pk, reciente.pk])
        self.assertEqual(self.ids(self.client.get(self.url, {'hasta': hasta})), [viejo.pk])

    def test_fecha_invalida_se_ignora(self):
        a = self.crear_pedido()
        self.assertEqual(self.ids(self.client.get(self.url, {'desde': '2026-13-45', 'hasta': 'hola'})), [a.pk])

    def test_busca_por_nombre_correo_o_telefono_del_cliente(self):
        a = self.crear_pedido(cliente=self.ana)
        b = self.crear_pedido(cliente=self.luis)
        self.assertEqual(self.ids(self.client.get(self.url, {'q': 'Ruiz'})), [a.pk])
        self.assertEqual(self.ids(self.client.get(self.url, {'q': 'luis@correo'})), [b.pk])
        self.assertEqual(self.ids(self.client.get(self.url, {'q': '3001112233'})), [a.pk])

    def test_busca_por_numero_de_pedido(self):
        self.crear_pedido()
        b = self.crear_pedido()
        self.assertIn(b.pk, self.ids(self.client.get(self.url, {'q': str(b.pk)})))

    def test_combina_filtros(self):
        self.crear_pedido(sede=self.centro, estado='entregado')
        self.crear_pedido(sede=self.norte, estado='recibido')
        c = self.crear_pedido(sede=self.norte, estado='entregado')
        r = self.client.get(self.url, {'sede': self.norte.id, 'estado': 'entregado'})
        self.assertEqual(self.ids(r), [c.pk])


class BuscarClientesTests(BusquedaBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('buscar_clientes')

    def nombres(self, respuesta):
        return [c.username for c in respuesta.context['pagina']]

    def test_cliente_recibe_403(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonimo_no_entra(self):
        self.client.logout()
        self.assertIn(self.client.get(self.url).status_code, (302, 403))

    def test_solo_lista_clientes(self):
        self.assertCountEqual(self.nombres(self.client.get(self.url)), ['ana', 'luis'])

    def test_busca_por_nombre_correo_y_telefono(self):
        self.assertEqual(self.nombres(self.client.get(self.url, {'q': 'Mora'})), ['luis'])
        self.assertEqual(self.nombres(self.client.get(self.url, {'q': 'ana@correo'})), ['ana'])
        self.assertEqual(self.nombres(self.client.get(self.url, {'q': '3109998877'})), ['luis'])

    def test_filtra_por_cuenta_activa_o_desactivada(self):
        User.objects.filter(pk=self.luis.pk).update(is_active=False)
        self.assertEqual(self.nombres(self.client.get(self.url, {'activo': 'si'})), ['ana'])
        self.assertEqual(self.nombres(self.client.get(self.url, {'activo': 'no'})), ['luis'])

    def test_muestra_cuantos_pedidos_tiene_cada_cliente(self):
        self.crear_pedido(cliente=self.ana)
        self.crear_pedido(cliente=self.ana)
        cuenta = {c.username: c.num_pedidos for c in self.client.get(self.url).context['pagina']}
        self.assertEqual(cuenta, {'ana': 2, 'luis': 0})
