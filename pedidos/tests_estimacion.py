from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from menu.models import Category, Product, Sede, SedeProduct, TopeCapacidad, ZonaCobertura
from users.models import Direccion
from .cart import Carrito
from .services import crear_pedido

User = get_user_model()


class TiempoEstimadoTests(TestCase):  # HU32
    def setUp(self):
        self.sede = Sede.objects.create(
            name='Centro', address='Cra 1', opening_time='00:00', closing_time='23:59',
        )
        self.cliente = User.objects.create_user('cli', password='x', role='cliente')
        self.direccion = Direccion.objects.create(
            user=self.cliente, label='Casa', address='Calle 10 # 5-20, San Fernando',
        )
        cat = Category.objects.create(name='Platos')
        self.prod = Product.objects.create(
            category=cat, name='Hamburguesa', description='Rica', price=Decimal('20000'),
        )
        SedeProduct.objects.create(sede=self.sede, product=self.prod, is_available=True)

    def _crear_con_carrito(self, tipo_entrega='domicilio'):
        session = self.client.session
        carrito = Carrito(type('Req', (), {'session': session})())
        carrito.agregar(self.prod.pk, self.sede.pk, 1, [])
        return crear_pedido(
            carrito,
            cliente=self.cliente,
            metodo_pago='efectivo',
            direccion=self.direccion if tipo_entrega == 'domicilio' else None,
            tipo_entrega=tipo_entrega,
        )

    def test_mostrador_no_suma_tiempo_de_domicilio(self):
        p_mostrador = self._crear_con_carrito(tipo_entrega='mostrador')
        p_domicilio = self._crear_con_carrito(tipo_entrega='domicilio')
        self.assertIsNotNone(p_mostrador.tiempo_estimado)
        self.assertGreater(p_domicilio.tiempo_estimado, p_mostrador.tiempo_estimado)

    def test_usa_tiempo_de_zona_de_cobertura(self):
        # Detecta dinámicamente el campo de tiempo en ZonaCobertura
        campo_tiempo = next(
            f.name for f in ZonaCobertura._meta.fields
            if 'tiempo' in f.name or 'min' in f.name
        )
        ZonaCobertura.objects.create(
            sede=self.sede,
            nombre='Zona Cercana',
            barrios='San Fernando',
            tarifa_domicilio=Decimal('3000'),
            **{campo_tiempo: 12},
        )
        pedido = self._crear_con_carrito(tipo_entrega='domicilio')
        self.assertEqual(pedido.tiempo_estimado, 27)  # 15 prep + 12 zona

    def test_aumenta_tiempo_cuando_cocina_tiene_alta_ocupacion(self):
        TopeCapacidad.objects.create(
            sede=self.sede, hora_inicio='00:00', hora_fin='23:59', max_pedidos=10,
        )
        for _ in range(8):
            self._crear_con_carrito(tipo_entrega='mostrador')
        pedido_congestionado = self._crear_con_carrito(tipo_entrega='mostrador')
        self.assertEqual(pedido_congestionado.tiempo_estimado, 30)  # 15 prep + 15 recargo (>=80%)