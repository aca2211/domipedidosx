from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from menu.models import Category, Product, Sede, SedeProduct
from users.models import Direccion

from .models import DetallePedido, Pedido

User = get_user_model()
URL = 'cargar_demo'


def cargar(**opciones):
    call_command(URL, stdout=StringIO(), **opciones)


def conteos():
    return {
        'sedes': Sede.objects.count(), 'categorias': Category.objects.count(),
        'productos': Product.objects.count(), 'sede_productos': SedeProduct.objects.count(),
        'usuarios': User.objects.count(), 'direcciones': Direccion.objects.count(),
        'pedidos': Pedido.objects.count(), 'detalles': DetallePedido.objects.count(),
    }


@override_settings(DEBUG=True)
class CargarDemoTests(TestCase):
    def test_crea_lo_que_pide_la_guia(self):
        cargar()
        c = conteos()
        self.assertEqual(c['sedes'], 2)
        self.assertEqual(c['categorias'], 3)
        self.assertEqual(c['productos'], 10)
        self.assertEqual(c['sede_productos'], 20)   # cada producto en cada sede
        self.assertEqual(
            set(User.objects.values_list('role', flat=True)), {'cliente', 'operador', 'cocina', 'admin'},
        )

    def test_hay_disponibilidad_distinta_por_sede(self):
        cargar()
        self.assertEqual(SedeProduct.objects.filter(is_available=False).count(), 1)
        agotado = SedeProduct.objects.get(is_available=False)
        self.assertEqual(agotado.sede.name, 'Sede Norte')

    def test_se_puede_correr_dos_veces_sin_duplicar(self):
        cargar()
        primera = conteos()
        cargar()
        self.assertEqual(conteos(), primera)

    def test_los_usuarios_entran_con_la_clave_demo(self):
        cargar()
        for username in ('demo_cliente', 'demo_operador', 'demo_cocina', 'demo_admin'):
            self.assertTrue(self.client.login(username=username, password='demo1234'), username)

    def test_no_pisa_a_un_admin_real(self):
        real = User.objects.create_superuser('admin', password='clave-real-1', role='admin')
        cargar()
        real.refresh_from_db()
        self.assertTrue(real.check_password('clave-real-1'))

    def test_pedidos_en_todos_los_estados_con_totales_coherentes(self):
        cargar()
        estados = set(Pedido.objects.values_list('estado', flat=True))
        self.assertEqual(estados, {'recibido', 'en_preparacion', 'listo', 'entregado', 'cancelado'})
        for pedido in Pedido.objects.prefetch_related('detalles'):
            self.assertEqual(pedido.subtotal, sum(d.subtotal for d in pedido.detalles.all()))
            self.assertEqual(pedido.total, pedido.subtotal + pedido.costo_domicilio)
            if pedido.tipo_entrega == 'domicilio':
                self.assertIsNotNone(pedido.direccion)

    def test_reiniciar_pedidos_recrea_los_del_cliente_demo(self):
        cargar()
        cliente = User.objects.get(username='demo_cliente')
        Pedido.objects.create(
            cliente=cliente, creado_por=cliente, sede=Sede.objects.first(),
            metodo_pago='efectivo', subtotal=1, total=1,
        )
        cargar(reiniciar_pedidos=True)
        self.assertEqual(Pedido.objects.count(), 7)

    def test_el_operador_entra_al_panel_y_al_admin_del_menu(self):
        cargar()
        self.client.login(username='demo_operador', password='demo1234')
        centro = Sede.objects.get(name='Sede Centro')
        panel = self.client.get(reverse('operador_panel') + f'?sede={centro.pk}')
        self.assertEqual(panel.status_code, 200)
        self.assertEqual(len(panel.context['pedidos']), 6)   # los de hoy en Sede Centro
        self.assertEqual(self.client.get('/admin/menu/').status_code, 200)

    def test_la_cocina_ve_pedidos_en_el_tablero(self):
        cargar()
        self.client.login(username='demo_cocina', password='demo1234')
        centro = Sede.objects.get(name='Sede Centro')
        columnas = self.client.get(reverse('cocina_tablero') + f'?sede={centro.pk}').context['columnas']
        self.assertEqual([len(c['pedidos']) for c in columnas], [2, 1, 1])

    def test_el_cliente_ve_sus_pedidos(self):
        cargar()
        self.client.login(username='demo_cliente', password='demo1234')
        r = self.client.get(reverse('mis_pedidos'))
        self.assertEqual(r.status_code, 200)


class CargarDemoSeguridadTests(TestCase):
    @override_settings(DEBUG=False)
    def test_no_corre_con_debug_apagado(self):
        with self.assertRaises(CommandError):
            cargar()
        self.assertEqual(User.objects.count(), 0)

    @override_settings(DEBUG=False)
    def test_force_lo_permite(self):
        cargar(force=True)
        self.assertEqual(Sede.objects.count(), 2)
