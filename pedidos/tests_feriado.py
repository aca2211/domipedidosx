from django.urls import reverse
from django.utils import timezone

from menu.models import Feriado

from .models import Pedido
from .tests import BaseTest


class FeriadoClienteTests(BaseTest):  # HU38
    def confirmar_siguiendo(self):
        return self.client.post(reverse('pedido_confirmar'), {
            'direccion': self.direccion.id, 'metodo_pago': 'efectivo', 'observaciones': '',
        }, follow=True)

    def test_en_feriado_no_se_crea_el_pedido(self):
        Feriado.objects.create(date=timezone.localdate(), name='Día de prueba')
        self.agregar(self.burger)
        respuesta = self.confirmar_siguiendo()
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(respuesta.redirect_chain[-1][0], reverse('carrito_ver'))

    def test_el_mensaje_menciona_el_feriado(self):
        Feriado.objects.create(date=timezone.localdate(), name='Día de prueba')
        self.agregar(self.burger)
        respuesta = self.confirmar_siguiendo()
        mensajes = [str(m) for m in respuesta.context['messages']]
        self.assertTrue(any('feriado' in m and 'Día de prueba' in m for m in mensajes))

    def test_en_feriado_el_carrito_se_conserva(self):
        Feriado.objects.create(date=timezone.localdate(), name='Día de prueba')
        self.agregar(self.burger)
        self.confirmar_siguiendo()
        self.assertEqual(self.carrito_sesion()['items'], {str(self.burger.id): 1})

    def test_feriado_de_otro_dia_no_bloquea(self):
        manana = timezone.localdate() + timezone.timedelta(days=1)
        Feriado.objects.create(date=manana, name='Mañana')
        self.agregar(self.burger)
        respuesta = self.confirmar()
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Pedido.objects.count(), 1)
