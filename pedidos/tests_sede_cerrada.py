from unittest import mock

from django.urls import reverse

from menu.models import Sede

from .models import Pedido
from .tests import BaseTest


class SedeCerradaClienteTests(BaseTest):  # HU47
    def confirmar_siguiendo(self):
        return self.client.post(reverse('pedido_confirmar'), {
            'direccion': self.direccion.id, 'metodo_pago': 'efectivo', 'observaciones': '',
        }, follow=True)

    def test_con_la_sede_abierta_se_crea_el_pedido(self):
        self.agregar(self.burger)
        with mock.patch.object(Sede, 'is_open_now', return_value=True):
            respuesta = self.confirmar()
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Pedido.objects.count(), 1)

    def test_con_la_sede_cerrada_no_se_crea_el_pedido(self):
        self.agregar(self.burger)
        with mock.patch.object(Sede, 'is_open_now', return_value=False):
            respuesta = self.confirmar_siguiendo()
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(respuesta.redirect_chain[-1][0], reverse('carrito_ver'))

    def test_el_mensaje_dice_que_esta_cerrada_y_el_horario(self):
        self.agregar(self.burger)
        with mock.patch.object(Sede, 'is_open_now', return_value=False):
            respuesta = self.confirmar_siguiendo()
        mensajes = [str(m) for m in respuesta.context['messages']]
        self.assertTrue(any('cerrada' in m and self.sede1.name in m for m in mensajes))
        self.assertTrue(any('10:00' in m and '22:00' in m for m in mensajes))

    def test_con_la_sede_cerrada_el_carrito_se_conserva(self):
        self.agregar(self.burger)
        with mock.patch.object(Sede, 'is_open_now', return_value=False):
            self.confirmar_siguiendo()
        self.assertEqual(self.carrito_sesion()['items'], {str(self.burger.id): 1})

    def test_en_pruebas_las_sedes_estan_abiertas_por_defecto(self):
        from datetime import time
        sede = Sede(name='Madrugada', address='X', opening_time=time(0, 0), closing_time=time(0, 1))
        self.assertTrue(sede.is_open_now())
