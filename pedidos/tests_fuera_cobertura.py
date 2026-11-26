"""Tests HU25: rechazar direcciones fuera de cobertura."""
from decimal import Decimal

from django.urls import reverse

from users.models import Direccion

from .models import Pedido
from .tests import BaseTest
from .tests_cobertura import crear_zona
from .tests_pedido_operador import OperadorPedidoBase


class ClienteFueraCoberturaTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.direccion.address = 'Calle 5 # 6-7, barrio Granada'
        self.direccion.save()
        self.zona = crear_zona(self.sede1, barrios='Granada', tarifa='3000')

    def test_hu25_rechaza_direccion_fuera_de_cobertura(self):
        fuera = Direccion.objects.create(user=self.cliente, label='Trabajo', address='Cra 1, barrio Aguablanca')
        self.agregar(self.burger)
        resp = self.confirmar(direccion=fuera.id)
        self.assertRedirects(resp, reverse('carrito_ver'))
        self.assertEqual(Pedido.objects.count(), 0)
        msg = ' '.join(str(m) for m in resp.wsgi_request._messages)
        self.assertIn('fuera de la cobertura', msg)
        self.assertIn('Granada', msg)           # dice qué barrios sí tienen cobertura

    def test_hu25_fuera_de_cobertura_no_vacia_el_carrito_ni_descuenta_stock(self):
        fuera = Direccion.objects.create(user=self.cliente, label='Trabajo', address='Cra 1, barrio Aguablanca')
        self.agregar(self.burger)
        self.confirmar(direccion=fuera.id)
        self.assertEqual(self.carrito_sesion()['items'], {str(self.burger.id): 1})

    def test_hu25_sugiere_otra_sede_que_si_cubre_la_direccion(self):
        crear_zona(self.sede2, 'Norte 1', 'Aguablanca')
        fuera = Direccion.objects.create(user=self.cliente, label='Trabajo', address='Cra 1, barrio Aguablanca')
        self.agregar(self.burger)
        resp = self.confirmar(direccion=fuera.id)
        msg = ' '.join(str(m) for m in resp.wsgi_request._messages)
        self.assertIn('sí tiene cobertura en: Norte', msg)

    def test_pantalla_confirmar_avisa_si_la_direccion_elegida_no_tiene_cobertura(self):
        self.direccion.address = 'Calle 5, barrio Aguablanca'
        self.direccion.save()
        self.agregar(self.burger)
        resp = self.client.get(reverse('pedido_confirmar'))
        self.assertIn('fuera de la cobertura', resp.context['aviso_cobertura'])


class OperadorFueraCoberturaTests(OperadorPedidoBase):
    def setUp(self):
        super().setUp()
        self.casa.address = 'Calle 1 # 2-3, barrio Granada'
        self.casa.save()
        self.zona = crear_zona(self.centro, barrios='Granada', tarifa='4000')
        self.elegir_cliente()
        self.agregar()    # burger 20.000

    def test_domicilio_fuera_de_cobertura_se_rechaza(self):
        fuera = Direccion.objects.create(user=self.ana, label='Otra', address='Cra 50, barrio Aguablanca')
        resp = self.confirmar(tipo_entrega='domicilio', direccion=fuera.id)
        self.assertRedirects(resp, reverse('operador_armar_pedido'))
        self.assertEqual(Pedido.objects.count(), 0)
