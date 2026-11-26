"""Tests HU27: sugerir otra sede o franja cuando la sede está llena."""
from datetime import datetime, time
from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from menu.models import Sede, SedeProduct, TopeCapacidad
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


class AlternativasBase(BaseTest):
    """Sede1 (Centro) llena con tope 4; sede2 (Norte) tiene cupo."""

    def setUp(self):
        super().setUp()
        parche = mock.patch('pedidos.capacidad.timezone.localtime', return_value=AHORA)
        parche.start()
        self.addCleanup(parche.stop)
        self.tope = TopeCapacidad.objects.create(
            sede=self.sede1, hora_inicio=time(12, 0), hora_fin=time(14, 0), max_pedidos=4,
        )
        for _ in range(4):
            _pedido_en(self.sede1, self.otro)

    def confirmar_siguiendo(self):
        return self.client.post(reverse('pedido_confirmar'), {
            'direccion': self.direccion.id, 'metodo_pago': 'efectivo', 'observaciones': '',
        }, follow=True)

    def mensaje(self):
        r = self.confirmar_siguiendo()
        return ' '.join(str(m) for m in r.context['messages'])


class SugerenciaDeSedAlternativaTests(AlternativasBase):
    def test_mensaje_incluye_sede_alternativa_con_cupo(self):
        # sede2 vende burger (configurado en BaseTest) y tiene cupo
        self.agregar(self.burger)
        self.assertIn(self.sede2.name, self.mensaje())

    def test_no_sugiere_sede_que_no_vende_todos_los_productos(self):
        # papas solo está en sede1, no en sede2
        self.agregar(self.papas)
        self.assertNotIn(self.sede2.name, self.mensaje())

    def test_no_sugiere_sede_con_producto_agotado(self):
        SedeProduct.objects.filter(sede=self.sede2, product=self.burger).update(is_available=False)
        self.agregar(self.burger)
        self.assertNotIn(self.sede2.name, self.mensaje())

    def test_no_sugiere_sede_que_tambien_esta_llena(self):
        TopeCapacidad.objects.create(
            sede=self.sede2, hora_inicio=time(12, 0), hora_fin=time(14, 0), max_pedidos=1,
        )
        _pedido_en(self.sede2, self.otro)
        self.agregar(self.burger)
        self.assertNotIn(self.sede2.name, self.mensaje())

    def test_no_sugiere_sede_cerrada(self):
        with mock.patch.object(Sede, 'is_open_now', side_effect=lambda s=None: False):
            self.agregar(self.burger)
            self.assertNotIn(self.sede2.name, self.mensaje())

    def test_no_sugiere_sede_inactiva(self):
        self.sede2.is_active = False
        self.sede2.save()
        self.agregar(self.burger)
        self.assertNotIn(self.sede2.name, self.mensaje())


class SugerenciaDeHoraTests(AlternativasBase):
    def test_mensaje_incluye_hora_en_que_termina_la_franja(self):
        self.agregar(self.burger)
        self.assertIn('14:00', self.mensaje())

    def test_no_sugiere_hora_si_la_sede_cierra_antes(self):
        # La sede cierra a las 14:00, igual que termina la franja → ya no reabre
        from menu.models import Sede as _Sede
        _Sede.objects.filter(pk=self.sede1.pk).update(closing_time=time(14, 0))
        self.sede1.refresh_from_db()
        self.agregar(self.burger)
        self.assertNotIn('a partir de las', self.mensaje())


class MensajeSinAlternativasTests(AlternativasBase):
    def test_mensaje_cuando_no_hay_ninguna_alternativa(self):
        # Agotamos burger en sede2 y cerramos la sede para que no haya sugerencias
        SedeProduct.objects.filter(sede=self.sede2, product=self.burger).update(is_available=False)
        from menu.models import Sede as _Sede
        _Sede.objects.filter(pk=self.sede1.pk).update(closing_time=time(14, 0))
        self.sede1.refresh_from_db()
        self.agregar(self.burger)
        msg = self.mensaje()
        self.assertIn('intenta de nuevo más tarde', msg)
        self.assertNotIn(self.sede2.name, msg)
