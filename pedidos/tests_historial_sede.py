from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from menu.models import Sede

from .models import Pedido

User = get_user_model()


class HistorialSedeTests(TestCase):  # HU44
    def setUp(self):
        self.centro = Sede.objects.create(name='Centro', address='Cra 1')
        self.norte = Sede.objects.create(name='Norte', address='Av 3')
        self.operador = User.objects.create_user('oper', password='x', role='operador', sede=self.centro)
        self.ana = User.objects.create_user('ana', password='x', role='cliente', first_name='Ana', last_name='Ruiz')
        self.client.force_login(self.operador)
        self.url = reverse('operador_historial')

    def crear_pedido(self, sede=None, estado='recibido', dias_atras=0):
        pedido = Pedido.objects.create(
            cliente=self.ana, creado_por=self.ana, sede=sede or self.centro,
            metodo_pago='efectivo', subtotal='38000', total='38000', estado=estado,
        )
        if dias_atras:  # auto_now_add impide fijar la fecha al crear
            Pedido.objects.filter(pk=pedido.pk).update(created_at=timezone.now() - timedelta(days=dias_atras))
        return pedido

    def ids(self, respuesta):
        return [p.pk for p in respuesta.context['pagina']]

    # --- acceso ---
    def test_cliente_recibe_403(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonimo_no_entra(self):
        self.client.logout()
        self.assertIn(self.client.get(self.url).status_code, (302, 403))

    def test_sin_sede_vuelve_al_panel(self):
        sin_sede = User.objects.create_user('sinsede', password='x', role='operador')
        self.client.force_login(sin_sede)
        self.assertRedirects(self.client.get(self.url), reverse('operador_panel'))

    # --- contenido ---
    def test_muestra_pedidos_de_hoy_y_de_dias_anteriores(self):
        hoy = self.crear_pedido()
        viejo = self.crear_pedido(dias_atras=10)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertCountEqual(self.ids(respuesta), [hoy.pk, viejo.pk])

    def test_no_muestra_pedidos_de_otra_sede(self):
        propio = self.crear_pedido()
        ajeno = self.crear_pedido(sede=self.norte)
        ids = self.ids(self.client.get(self.url))
        self.assertIn(propio.pk, ids)
        self.assertNotIn(ajeno.pk, ids)

    def test_el_mas_reciente_va_primero(self):
        viejo = self.crear_pedido(dias_atras=3)
        nuevo = self.crear_pedido()
        self.assertEqual(self.ids(self.client.get(self.url)), [nuevo.pk, viejo.pk])

    def test_muestra_el_nombre_del_cliente_y_el_total(self):
        self.crear_pedido()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Ana Ruiz')
        self.assertContains(respuesta, '$38000')

    def test_sin_pedidos_muestra_mensaje_vacio(self):
        self.assertContains(self.client.get(self.url), 'No hay pedidos para mostrar')

    # --- filtro por estado ---
    def test_filtra_por_estado(self):
        entregado = self.crear_pedido(estado='entregado')
        self.crear_pedido(estado='recibido')
        self.assertEqual(self.ids(self.client.get(self.url, {'estado': 'entregado'})), [entregado.pk])

    def test_estado_invalido_se_ignora(self):
        a = self.crear_pedido(estado='entregado')
        b = self.crear_pedido(estado='recibido')
        respuesta = self.client.get(self.url, {'estado': 'inventado'})
        self.assertCountEqual(self.ids(respuesta), [a.pk, b.pk])

    # --- paginación ---
    def test_pagina_de_a_25_pedidos(self):
        for _ in range(30):
            self.crear_pedido()
        self.assertEqual(len(self.ids(self.client.get(self.url))), 25)
        self.assertEqual(len(self.ids(self.client.get(self.url, {'page': 2}))), 5)

    def test_pagina_inexistente_muestra_la_ultima(self):
        for _ in range(30):
            self.crear_pedido()
        self.assertEqual(len(self.ids(self.client.get(self.url, {'page': 99}))), 5)

    # --- enlace desde el panel ---
    def test_el_panel_enlaza_al_historial(self):
        self.assertContains(self.client.get(reverse('operador_panel')), self.url)
