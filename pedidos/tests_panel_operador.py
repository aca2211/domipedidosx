from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.template.defaultfilters import floatformat
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from menu.models import Sede
from .models import Pedido

User = get_user_model()


class PanelOperadorTests(TestCase):  # HU21
    def setUp(self):
        self.operador = User.objects.create_user('operador1', password='x', role='operador')
        self.ana = User.objects.create_user('ana', password='x', role='cliente', first_name='Ana', last_name='Ruiz')
        self.beto = User.objects.create_user('beto', password='x', role='cliente')
        self.centro = Sede.objects.create(name='Centro', address='Cra 1')
        self.norte = Sede.objects.create(name='Norte', address='Av 3')
        self.client.force_login(self.operador)
        self.url = reverse('operador_panel')
        self.url_centro = f'{self.url}?sede={self.centro.pk}'

    def crear_pedido(self, sede=None, cliente=None, estado='recibido', total='38000', dias_atras=0):
        pedido = Pedido.objects.create(
            cliente=cliente or self.ana, creado_por=cliente or self.ana,
            sede=sede or self.centro, metodo_pago='efectivo',
            subtotal=total, total=total, estado=estado,
        )
        if dias_atras:  # auto_now_add impide fijar la fecha al crear
            Pedido.objects.filter(pk=pedido.pk).update(created_at=timezone.now() - timedelta(days=dias_atras))
        return pedido

    # --- acceso por rol ---
    def test_anonimo_va_al_login(self):
        self.client.logout()
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)

    def test_otros_roles_reciben_403(self):
        for username, role in [('cli', 'cliente'), ('coc', 'cocina'), ('rep', 'repartidor'), ('adm', 'admin')]:
            self.client.force_login(User.objects.create_user(username, password='x', role=role))
            self.assertEqual(self.client.get(self.url).status_code, 403, role)

    # --- sede ---
    def test_sin_sede_muestra_selector(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context['sede'])
        self.assertEqual(len(r.context['sedes']), 2)

    def test_recuerda_la_sede_elegida(self):
        self.client.get(self.url_centro)
        r = self.client.get(self.url)
        self.assertEqual(r.context['sede'], self.centro)

    def test_sede_invalida_o_inactiva_se_ignora(self):
        self.assertIsNone(self.client.get(self.url + '?sede=abc').context['sede'])
        self.assertIsNone(self.client.get(self.url + '?sede=9999').context['sede'])
        Sede.objects.filter(pk=self.centro.pk).update(is_active=False)
        self.assertIsNone(self.client.get(self.url_centro).context['sede'])

    # --- contenido ---
    def test_solo_pedidos_de_hoy_y_de_la_sede(self):
        hoy = self.crear_pedido()
        self.crear_pedido(sede=self.norte)          # otra sede
        self.crear_pedido(dias_atras=1)             # de ayer
        r = self.client.get(self.url_centro)
        self.assertEqual(list(r.context['pedidos']), [hoy])

    def test_muestra_hora_cliente_estado_y_total(self):
        p = self.crear_pedido(estado='en_preparacion', total='38000')
        r = self.client.get(self.url_centro)
        self.assertContains(r, timezone.localtime(p.created_at).strftime('%H:%M'))
        self.assertContains(r, 'Ana Ruiz')                       # nombre completo
        self.assertContains(r, p.get_estado_display())
        self.assertContains(r, f'${floatformat(p.total, 0)}')

    def test_cliente_sin_nombre_muestra_su_usuario(self):
        self.crear_pedido(cliente=self.beto)
        self.assertContains(self.client.get(self.url_centro), 'beto')

    def test_el_mas_reciente_va_primero(self):
        primero = self.crear_pedido()
        segundo = self.crear_pedido()
        r = self.client.get(self.url_centro)
        self.assertEqual(list(r.context['pedidos']), [segundo, primero])

    def test_dia_vacio_muestra_mensaje(self):
        self.assertContains(self.client.get(self.url_centro), 'Aún no hay pedidos hoy')

    def test_tiene_enlaces_a_los_modulos(self):
        r = self.client.get(self.url_centro)
        self.assertContains(r, reverse('operador_elegir_cliente'))
        self.assertContains(r, reverse('menu_list'))
        self.assertContains(r, '/admin/menu/')

    def test_no_hace_una_consulta_por_pedido(self):
        self.crear_pedido()
        with CaptureQueriesContext(connection) as con_uno:
            self.client.get(self.url_centro)
        for _ in range(4):
            self.crear_pedido()
        with CaptureQueriesContext(connection) as con_cinco:
            self.client.get(self.url_centro)
        self.assertEqual(len(con_uno), len(con_cinco))
