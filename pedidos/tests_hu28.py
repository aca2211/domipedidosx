"""Tests HU28: alerta al operador cuando la cocina se acerca al límite."""
from datetime import datetime, time
from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from menu.models import Sede, TopeCapacidad
from .capacidad import EstadoCapacidad, estado_capacidad
from .models import Pedido
from .tests import BaseTest

User = get_user_model()

AHORA = timezone.make_aware(datetime(2026, 11, 23, 12, 30))


def _pedido_en(sede, cliente, momento=AHORA, estado='recibido'):
    p = Pedido.objects.create(
        cliente=cliente, creado_por=cliente, sede=sede,
        metodo_pago='efectivo', subtotal=1000, total=1000, estado=estado,
    )
    Pedido.objects.filter(pk=p.pk).update(created_at=momento)
    return p


class EstadoCapacidadTests(BaseTest):
    """Cálculo de ocupación y umbrales (HU28)."""

    def setUp(self):
        super().setUp()
        parche = mock.patch('pedidos.capacidad.timezone.localtime', return_value=AHORA)
        parche.start()
        self.addCleanup(parche.stop)
        self.tope = TopeCapacidad.objects.create(
            sede=self.sede1, hora_inicio=time(12, 0), hora_fin=time(14, 0),
            max_pedidos=5, umbral_alerta=80,
        )

    def llenar(self, n):
        for _ in range(n):
            _pedido_en(self.sede1, self.otro)

    def test_sin_tope_devuelve_none(self):
        self.tope.delete()
        self.assertIsNone(estado_capacidad(self.sede1))

    def test_devuelve_ocupados_correctos(self):
        self.llenar(3)
        estado = estado_capacidad(self.sede1)
        self.assertEqual(estado.ocupados, 3)
        self.assertEqual(estado.cupos, 2)
        self.assertEqual(estado.porcentaje, 60)

    def test_por_debajo_del_umbral_no_hay_alerta(self):
        self.llenar(3)   # 60 %, umbral 80 %
        self.assertFalse(estado_capacidad(self.sede1).cerca_del_limite)
        self.assertFalse(estado_capacidad(self.sede1).lleno)

    def test_al_llegar_al_umbral_se_activa_la_alerta(self):
        self.llenar(4)   # 4/5 = 80 %, igual al umbral
        estado = estado_capacidad(self.sede1)
        self.assertTrue(estado.cerca_del_limite)
        self.assertFalse(estado.lleno)

    def test_lleno_no_es_cerca_del_limite(self):
        self.llenar(5)
        estado = estado_capacidad(self.sede1)
        self.assertTrue(estado.lleno)
        self.assertFalse(estado.cerca_del_limite)
        self.assertEqual(estado.cupos, 0)

    def test_umbral_configurable(self):
        self.tope.umbral_alerta = 50
        self.tope.save()
        self.llenar(3)   # 60 % > 50 %
        self.assertTrue(estado_capacidad(self.sede1).cerca_del_limite)

    def test_fuera_de_la_franja_devuelve_none(self):
        tarde = timezone.make_aware(datetime(2026, 11, 23, 15, 0))
        with mock.patch('pedidos.capacidad.timezone.localtime', return_value=tarde):
            self.assertIsNone(estado_capacidad(self.sede1))


class AlertaPanelOperadorTests(BaseTest):
    """La alerta aparece correctamente en el panel del operador (HU28)."""

    def setUp(self):
        super().setUp()
        parche = mock.patch('pedidos.capacidad.timezone.localtime', return_value=AHORA)
        parche.start()
        self.addCleanup(parche.stop)
        self.operador = User.objects.create_user(
            'oper', password='x', role='operador', sede=self.sede1,
        )
        self.client.force_login(self.operador)
        self.tope = TopeCapacidad.objects.create(
            sede=self.sede1, hora_inicio=time(12, 0), hora_fin=time(14, 0),
            max_pedidos=5, umbral_alerta=80,
        )
        self.url = reverse('operador_panel')

    def llenar(self, n):
        for _ in range(n):
            _pedido_en(self.sede1, self.otro)

    def test_sin_tope_no_muestra_alerta(self):
        self.tope.delete()
        r = self.client.get(self.url)
        self.assertNotContains(r, 'alert-warning')
        self.assertNotContains(r, 'alert-danger')

    def test_bajo_el_umbral_no_muestra_alerta(self):
        self.llenar(3)   # 60 %
        r = self.client.get(self.url)
        self.assertNotContains(r, 'alert-warning')
        self.assertNotContains(r, 'alert-danger')

    def test_en_el_umbral_muestra_alerta_amarilla(self):
        self.llenar(4)   # 80 %
        r = self.client.get(self.url)
        self.assertContains(r, 'alert-warning')
        self.assertContains(r, 'La cocina se acerca al límite')
        self.assertContains(r, 'Van 4 de 5 pedidos')

    def test_lleno_muestra_alerta_roja(self):
        self.llenar(5)
        r = self.client.get(self.url)
        self.assertContains(r, 'alert-danger')
        self.assertContains(r, 'Cocina al límite')

    def test_alerta_es_solo_de_su_sede(self):
        self.llenar(5)   # sede1 llena
        otro_operador = User.objects.create_user(
            'oper2', password='x', role='operador', sede=self.sede2,
        )
        self.client.force_login(otro_operador)
        r = self.client.get(self.url)
        self.assertNotContains(r, 'alert-danger')
