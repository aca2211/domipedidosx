"""Tests HU26: topes de pedidos por sede y franja horaria."""
from datetime import datetime, time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from menu.models import Category, Product, Sede, SedeProduct, TopeCapacidad
from .models import Pedido
from .tests import BaseTest
from .tests_pedido_operador import OperadorPedidoBase

User = get_user_model()

AHORA = timezone.make_aware(datetime(2026, 11, 23, 12, 30))  # 12:30, dentro de la franja de prueba


def _crear_pedido_en(sede, cliente, momento=AHORA, estado='recibido'):
    """Pedido de prueba con la fecha fijada (auto_now_add impide fijarla al crear)."""
    pedido = Pedido.objects.create(
        cliente=cliente, creado_por=cliente, sede=sede,
        metodo_pago='efectivo', subtotal=1000, total=1000, estado=estado,
    )
    Pedido.objects.filter(pk=pedido.pk).update(created_at=momento)
    return pedido


# ---------------------------------------------------------------------------
# Modelo TopeCapacidad
# ---------------------------------------------------------------------------

class TopeCapacidadModeloTests(BaseTest):
    def tope(self, inicio=time(12, 0), fin=time(14, 0), maximo=4, **extra):
        return TopeCapacidad(
            sede=self.sede1, hora_inicio=inicio, hora_fin=fin,
            max_pedidos=maximo, **extra,
        )

    def test_tope_valido_se_guarda(self):
        t = self.tope()
        t.full_clean()
        t.save()
        self.assertEqual(t.max_pedidos, 4)
        self.assertTrue(t.is_active)

    def test_hora_fin_debe_ser_posterior_a_inicio(self):
        for ini, fin in [(time(14, 0), time(12, 0)), (time(12, 0), time(12, 0))]:
            with self.assertRaises(ValidationError) as ctx:
                self.tope(inicio=ini, fin=fin).full_clean()
            self.assertIn('hora_fin', ctx.exception.message_dict)

    def test_max_pedidos_debe_ser_al_menos_1(self):
        with self.assertRaises(ValidationError) as ctx:
            self.tope(maximo=0).full_clean()
        self.assertIn('max_pedidos', ctx.exception.message_dict)

    def test_no_se_permiten_franjas_solapadas_en_la_misma_sede(self):
        self.tope().save()
        with self.assertRaises(ValidationError):
            self.tope(inicio=time(13, 0), fin=time(15, 0)).full_clean()

    def test_franjas_contiguas_no_se_solapan(self):
        self.tope().save()
        self.tope(inicio=time(14, 0), fin=time(16, 0)).full_clean()   # no lanza

    def test_otra_sede_puede_usar_la_misma_franja(self):
        self.tope().save()
        TopeCapacidad(
            sede=self.sede2, hora_inicio=time(12, 0), hora_fin=time(14, 0), max_pedidos=4,
        ).full_clean()

    def test_tope_inactivo_no_bloquea_nueva_franja_solapada(self):
        self.tope(is_active=False).save()
        self.tope(inicio=time(13, 0), fin=time(15, 0)).full_clean()   # no lanza

    def test_editar_un_tope_no_choca_consigo_mismo(self):
        t = self.tope()
        t.save()
        t.max_pedidos = 10
        t.full_clean()   # no lanza

    def test_vigente_devuelve_tope_de_la_hora(self):
        t = self.tope()
        t.save()
        self.assertEqual(TopeCapacidad.vigente(self.sede1, time(12, 0)), t)
        self.assertEqual(TopeCapacidad.vigente(self.sede1, time(13, 59)), t)

    def test_vigente_fin_es_exclusivo(self):
        self.tope().save()
        self.assertIsNone(TopeCapacidad.vigente(self.sede1, time(14, 0)))

    def test_vigente_fuera_de_franja_devuelve_none(self):
        self.tope().save()
        self.assertIsNone(TopeCapacidad.vigente(self.sede1, time(10, 0)))

    def test_vigente_ignora_topes_inactivos(self):
        self.tope(is_active=False).save()
        self.assertIsNone(TopeCapacidad.vigente(self.sede1, time(13, 0)))

    def test_vigente_no_cruza_sedes(self):
        self.tope().save()
        self.assertIsNone(TopeCapacidad.vigente(self.sede2, time(13, 0)))


# ---------------------------------------------------------------------------
# Verificación del tope al confirmar el pedido (cliente)
# ---------------------------------------------------------------------------

class TopeAlConfirmarTests(BaseTest):
    def setUp(self):
        super().setUp()
        parche = mock.patch('pedidos.capacidad.timezone.localtime', return_value=AHORA)
        parche.start()
        self.addCleanup(parche.stop)
        self.tope = TopeCapacidad.objects.create(
            sede=self.sede1, hora_inicio=time(12, 0), hora_fin=time(14, 0), max_pedidos=4,
        )

    def llenar(self, n, sede=None, **kw):
        for _ in range(n):
            _crear_pedido_en(sede or self.sede1, self.otro, **kw)

    def confirmar_siguiendo(self):
        return self.client.post(reverse('pedido_confirmar'), {
            'direccion': self.direccion.id, 'metodo_pago': 'efectivo', 'observaciones': '',
        }, follow=True)

    def mensajes(self, respuesta):
        return ' '.join(str(m) for m in respuesta.context['messages'])

    # --- pedidos que se crean ---

    def test_bajo_el_tope_se_crea_el_pedido(self):
        self.llenar(3)
        self.agregar(self.burger)
        self.assertEqual(self.confirmar().status_code, 302)
        self.assertEqual(Pedido.objects.filter(cliente=self.cliente).count(), 1)

    def test_sin_tope_no_hay_limite(self):
        self.tope.delete()
        self.llenar(30)
        self.agregar(self.burger)
        self.assertEqual(self.confirmar().status_code, 302)

    def test_tope_inactivo_no_limita(self):
        self.tope.is_active = False
        self.tope.save()
        self.llenar(10)
        self.agregar(self.burger)
        self.assertEqual(self.confirmar().status_code, 302)

    def test_pedidos_cancelados_no_cuentan_para_el_tope(self):
        self.llenar(4, estado='cancelado')
        self.agregar(self.burger)
        self.assertEqual(self.confirmar().status_code, 302)

    def test_pedidos_fuera_de_la_franja_no_cuentan(self):
        antes = timezone.make_aware(datetime(2026, 11, 23, 11, 59))
        despues = timezone.make_aware(datetime(2026, 11, 23, 14, 0))
        self.llenar(2, momento=antes)
        self.llenar(2, momento=despues)
        self.agregar(self.burger)
        self.assertEqual(self.confirmar().status_code, 302)

    def test_pedidos_de_ayer_no_cuentan(self):
        self.llenar(4, momento=timezone.make_aware(datetime(2026, 11, 22, 12, 30)))
        self.agregar(self.burger)
        self.assertEqual(self.confirmar().status_code, 302)

    def test_pedidos_de_otra_sede_no_cuentan(self):
        self.llenar(10, sede=self.sede2)
        self.agregar(self.burger)
        self.assertEqual(self.confirmar().status_code, 302)

    def test_tope_aplica_por_separado_a_cada_sede(self):
        self.llenar(4, sede=self.sede1)   # Centro lleno
        self.agregar(self.burger, sede=self.sede2)
        self.assertEqual(self.confirmar().status_code, 302)

    def test_fuera_de_la_franja_no_hay_limite(self):
        self.llenar(4)
        tarde = timezone.make_aware(datetime(2026, 11, 23, 15, 0))
        with mock.patch('pedidos.capacidad.timezone.localtime', return_value=tarde):
            self.agregar(self.burger)
            self.assertEqual(self.confirmar().status_code, 302)

    # --- pedidos que se rechazan ---

    def test_en_el_tope_se_rechaza_el_pedido(self):
        self.llenar(4)
        self.agregar(self.burger)
        respuesta = self.confirmar_siguiendo()
        self.assertEqual(Pedido.objects.filter(cliente=self.cliente).count(), 0)
        self.assertEqual(respuesta.redirect_chain[-1][0], reverse('carrito_ver'))

    def test_mensaje_indica_el_tope_y_la_franja(self):
        self.llenar(4)
        self.agregar(self.burger)
        msg = self.mensajes(self.confirmar_siguiendo())
        self.assertIn('tope de 4 pedidos', msg)
        self.assertIn('12:00–14:00', msg)

    def test_al_rechazar_el_carrito_se_conserva(self):
        self.llenar(4)
        self.agregar(self.burger)
        self.confirmar_siguiendo()
        self.assertEqual(self.carrito_sesion()['items'], {str(self.burger.id): 1})


# ---------------------------------------------------------------------------
# Verificación del tope al confirmar el pedido (operador)
# ---------------------------------------------------------------------------

class TopeEnPedidoDelOperadorTests(OperadorPedidoBase):
    def test_operador_tampoco_puede_superar_el_tope(self):
        with mock.patch('pedidos.capacidad.timezone.localtime', return_value=AHORA):
            TopeCapacidad.objects.create(
                sede=self.centro, hora_inicio=time(12, 0), hora_fin=time(14, 0), max_pedidos=1,
            )
            _crear_pedido_en(self.centro, self.beto)
            self.elegir_cliente()
            self.agregar()
            respuesta = self.client.post(reverse('operador_confirmar'), {
                'tipo_entrega': 'mostrador', 'metodo_pago': 'efectivo', 'observaciones': '',
            }, follow=True)
        self.assertEqual(Pedido.objects.filter(cliente=self.ana).count(), 0)
        msg = ' '.join(str(m) for m in respuesta.context['messages'])
        self.assertIn('tope de 1 pedidos', msg)
