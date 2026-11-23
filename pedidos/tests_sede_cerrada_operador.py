from unittest import mock

from django.urls import reverse

from menu.models import Sede

from .models import Pedido
from .tests_pedido_operador import OperadorPedidoBase


class SedeCerradaOperadorTests(OperadorPedidoBase):  # HU47
    def preparar(self):
        self.elegir_cliente()
        self.agregar()

    def test_con_la_sede_abierta_el_operador_crea_el_pedido(self):
        self.preparar()
        with mock.patch.object(Sede, 'is_open_now', return_value=True):
            self.confirmar()
        self.assertEqual(Pedido.objects.count(), 1)

    def test_con_la_sede_cerrada_el_operador_no_crea_el_pedido(self):
        self.preparar()
        with mock.patch.object(Sede, 'is_open_now', return_value=False):
            respuesta = self.client.post(reverse('operador_confirmar'), {
                'tipo_entrega': 'mostrador', 'metodo_pago': 'efectivo', 'observaciones': '',
            }, follow=True)
        self.assertEqual(Pedido.objects.count(), 0)
        mensajes = [str(m) for m in respuesta.context['messages']]
        self.assertTrue(any('cerrada' in m for m in mensajes))
