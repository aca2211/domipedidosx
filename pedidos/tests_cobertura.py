"""Tests HU24: zonas de cobertura con tarifa, tiempo estimado y pedido mínimo."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.urls import reverse

from menu.models import ParametrosGlobales, ZonaCobertura, normalizar
from users.models import Direccion

from .models import Pedido
from .tests import BaseTest
from .tests_pedido_operador import OperadorPedidoBase


def crear_zona(sede, nombre='Zona 1', barrios='Granada, San Fernando', tarifa='3000', minimo=None, **extra):
    return ZonaCobertura.objects.create(
        sede=sede, nombre=nombre, barrios=barrios,
        tarifa_domicilio=Decimal(tarifa),
        pedido_minimo=None if minimo is None else Decimal(minimo), **extra,
    )


# ---------------------------------------------------------------------------
# Modelo ZonaCobertura (HU24)
# ---------------------------------------------------------------------------

class ZonaModeloTests(BaseTest):
    def test_normalizar_quita_tildes_mayusculas_y_signos(self):
        self.assertEqual(normalizar('Calle 5 # 38-10, Barrio SAN Fernández'), 'calle 5 38 10 barrio san fernandez')

    def test_lista_de_barrios_acepta_lineas_y_comas(self):
        zona = crear_zona(self.sede1, barrios='Granada\nSan Fernando, Centenario;  Peñón ')
        self.assertEqual(zona.lista_barrios, ['Granada', 'San Fernando', 'Centenario', 'Peñón'])

    def test_zona_valida_se_guarda(self):
        zona = ZonaCobertura(sede=self.sede1, nombre='Z', barrios='Granada', tarifa_domicilio=Decimal('2500'))
        zona.full_clean()
        zona.save()
        self.assertTrue(zona.is_active)
        self.assertEqual(zona.tiempo_estimado_min, 30)

    def test_exige_al_menos_un_barrio(self):
        zona = ZonaCobertura(sede=self.sede1, nombre='Z', barrios=' ,\n ', tarifa_domicilio=0)
        with self.assertRaises(ValidationError) as ctx:
            zona.full_clean()
        self.assertIn('barrios', ctx.exception.message_dict)

    def test_tarifa_y_minimo_no_pueden_ser_negativos(self):
        zona = ZonaCobertura(sede=self.sede1, nombre='Z', barrios='Granada',
                             tarifa_domicilio=Decimal('-1'), pedido_minimo=Decimal('-5'))
        with self.assertRaises(ValidationError) as ctx:
            zona.full_clean()
        self.assertIn('tarifa_domicilio', ctx.exception.message_dict)
        self.assertIn('pedido_minimo', ctx.exception.message_dict)

    def test_tiempo_estimado_debe_ser_al_menos_1(self):
        zona = ZonaCobertura(sede=self.sede1, nombre='Z', barrios='Granada', tiempo_estimado_min=0)
        with self.assertRaises(ValidationError) as ctx:
            zona.full_clean()
        self.assertIn('tiempo_estimado_min', ctx.exception.message_dict)

    def test_un_barrio_no_puede_estar_en_dos_zonas_activas_de_la_sede(self):
        crear_zona(self.sede1, 'Zona 1', 'Granada, Centenario')
        otra = ZonaCobertura(sede=self.sede1, nombre='Zona 2', barrios='granada', tarifa_domicilio=0)
        with self.assertRaises(ValidationError) as ctx:
            otra.full_clean()
        self.assertIn('barrios', ctx.exception.message_dict)

    def test_otra_sede_o_zona_inactiva_pueden_repetir_barrio(self):
        crear_zona(self.sede1, 'Zona 1', 'Granada')
        ZonaCobertura(sede=self.sede2, nombre='Zona 1', barrios='Granada', tarifa_domicilio=0).full_clean()
        ZonaCobertura(sede=self.sede1, nombre='Zona 2', barrios='Granada', tarifa_domicilio=0,
                      is_active=False).full_clean()

    def test_editar_una_zona_no_choca_consigo_misma(self):
        zona = crear_zona(self.sede1, barrios='Granada')
        zona.tarifa_domicilio = Decimal('4000')
        zona.full_clean()

    def test_nombre_de_zona_unico_por_sede(self):
        crear_zona(self.sede1, 'Zona 1', 'Granada')
        with self.assertRaises(ValidationError):
            ZonaCobertura(sede=self.sede1, nombre='Zona 1', barrios='Centenario', tarifa_domicilio=0).full_clean()

    def test_minimo_vacio_usa_el_global_y_cero_es_sin_minimo(self):
        ParametrosGlobales.objects.update_or_create(pk=1, defaults={'pedido_minimo_global': Decimal('12000')})
        self.assertEqual(crear_zona(self.sede1, 'A', 'Granada').minimo_efectivo(), Decimal('12000'))
        self.assertEqual(crear_zona(self.sede1, 'B', 'Centenario', minimo='0').minimo_efectivo(), Decimal('0'))
        self.assertEqual(crear_zona(self.sede1, 'C', 'Peñón', minimo='20000').minimo_efectivo(), Decimal('20000'))


class ZonaParaDireccionTests(BaseTest):
    def dir_de(self, texto):
        return Direccion(user=self.cliente, label='X', address=texto)

    def test_encuentra_la_zona_aunque_cambien_mayusculas_y_tildes(self):
        zona = crear_zona(self.sede1, barrios='San Fernando')
        self.assertEqual(ZonaCobertura.para_direccion(self.sede1, self.dir_de('Cra 9 # 4-5, BARRIO SAN FERNANDO')), zona)

    def test_sin_coincidencia_devuelve_none(self):
        crear_zona(self.sede1, barrios='Granada')
        self.assertIsNone(ZonaCobertura.para_direccion(self.sede1, self.dir_de('Calle 5, barrio Aguablanca')))

    def test_el_barrio_debe_coincidir_completo(self):
        crear_zona(self.sede1, barrios='Sur')
        self.assertIsNone(ZonaCobertura.para_direccion(self.sede1, self.dir_de('Calle 5, barrio Surameris')))

    def test_zona_inactiva_no_cubre(self):
        crear_zona(self.sede1, barrios='Granada', is_active=False)
        self.assertIsNone(ZonaCobertura.para_direccion(self.sede1, self.dir_de('Calle 5, Granada')))

    def test_zona_de_otra_sede_no_cubre(self):
        crear_zona(self.sede2, barrios='Granada')
        self.assertIsNone(ZonaCobertura.para_direccion(self.sede1, self.dir_de('Calle 5, Granada')))

    def test_gana_el_barrio_mas_especifico(self):
        crear_zona(self.sede1, 'Cerca', 'San Fernando', tarifa='2000')
        lejos = crear_zona(self.sede1, 'Lejos', 'San Fernando Viejo', tarifa='6000')
        self.assertEqual(ZonaCobertura.para_direccion(self.sede1, self.dir_de('Cra 9, San Fernando Viejo')), lejos)


# ---------------------------------------------------------------------------
# Cliente: tarifa y pedido mínimo por zona (HU24)
# ---------------------------------------------------------------------------

class ClienteCoberturaTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.direccion.address = 'Calle 5 # 6-7, barrio Granada'
        self.direccion.save()
        self.zona = crear_zona(self.sede1, barrios='Granada', tarifa='3000')

    def test_sede_sin_zonas_no_restringe_ni_cobra(self):
        self.zona.delete()
        self.agregar(self.burger)
        self.confirmar()
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.costo_domicilio, Decimal('0'))
        self.assertEqual(pedido.total, Decimal('15000'))

    def test_hu24_cobra_la_tarifa_de_la_zona(self):
        self.agregar(self.burger)
        self.confirmar()
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.costo_domicilio, Decimal('3000'))
        self.assertEqual(pedido.subtotal, Decimal('15000'))
        self.assertEqual(pedido.total, Decimal('18000'))

    def test_hu24_pedido_minimo_de_la_zona(self):
        self.zona.pedido_minimo = Decimal('20000')
        self.zona.save()
        self.agregar(self.burger)             # 15.000 < 20.000
        self.confirmar()
        self.assertEqual(Pedido.objects.count(), 0)
        self.agregar(self.papas)              # 23.000 >= 20.000
        self.confirmar()
        self.assertEqual(Pedido.objects.count(), 1)

    def test_hu24_usa_el_minimo_global_si_la_zona_no_define_uno(self):
        ParametrosGlobales.objects.update_or_create(pk=1, defaults={'pedido_minimo_global': Decimal('20000')})
        self.agregar(self.burger)
        resp = self.confirmar()
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertIn('pedido mínimo', ' '.join(str(m) for m in resp.wsgi_request._messages))

    def test_minimo_cero_en_la_zona_ignora_el_global(self):
        ParametrosGlobales.objects.update_or_create(pk=1, defaults={'pedido_minimo_global': Decimal('50000')})
        self.zona.pedido_minimo = Decimal('0')
        self.zona.save()
        self.agregar(self.burger)
        self.confirmar()
        self.assertEqual(Pedido.objects.count(), 1)

    def test_el_minimo_se_compara_con_el_subtotal_sin_domicilio(self):
        self.zona.pedido_minimo = Decimal('16000')
        self.zona.tarifa_domicilio = Decimal('3000')   # subtotal 15.000 + domicilio 3.000 = 18.000, pero subtotal < 16.000
        self.zona.save()
        self.agregar(self.burger)
        self.confirmar()
        self.assertEqual(Pedido.objects.count(), 0)

    def test_pantalla_confirmar_muestra_la_tarifa_de_la_direccion_principal(self):
        self.agregar(self.burger)
        resp = self.client.get(reverse('pedido_confirmar'))
        self.assertEqual(resp.context['costo_domicilio'], Decimal('3000'))
        self.assertEqual(resp.context['total'], Decimal('18000'))
        self.assertIsNone(resp.context['aviso_cobertura'])
        self.assertContains(resp, 'costos-direccion')

    def test_carrito_dice_que_el_domicilio_depende_de_la_zona(self):
        self.agregar(self.burger)
        resp = self.client.get(reverse('carrito_ver'))
        self.assertTrue(resp.context['domicilio_por_zona'])
        self.assertContains(resp, 'Según tu zona')

    def test_carrito_sin_zonas_muestra_el_costo_normal(self):
        self.zona.delete()
        self.agregar(self.burger)
        resp = self.client.get(reverse('carrito_ver'))
        self.assertFalse(resp.context['domicilio_por_zona'])
        self.assertNotContains(resp, 'Según tu zona')

    def test_resumen_sin_direccion_no_cobra_domicilio(self):
        from .cart import Carrito
        self.agregar(self.burger)
        req = self.client.get(reverse('carrito_ver')).wsgi_request
        self.assertEqual(Carrito(req).resumen()['costo_domicilio'], Decimal('0'))
        self.assertEqual(Carrito(req).resumen(direccion=self.direccion)['costo_domicilio'], Decimal('3000'))


# ---------------------------------------------------------------------------
# Operador: pedido a nombre del cliente (HU15 + HU24)
# ---------------------------------------------------------------------------

class OperadorCoberturaTests(OperadorPedidoBase):
    def setUp(self):
        super().setUp()
        self.casa.address = 'Calle 1 # 2-3, barrio Granada'
        self.casa.save()
        self.zona = crear_zona(self.centro, barrios='Granada', tarifa='4000')
        self.elegir_cliente()
        self.agregar()    # burger 20.000

    def test_domicilio_cubierto_cobra_la_tarifa(self):
        self.confirmar(tipo_entrega='domicilio', direccion=self.casa.id)
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.costo_domicilio, Decimal('4000'))
        self.assertEqual(pedido.total, Decimal('24000'))

    def test_mostrador_no_cobra_domicilio_ni_valida_zona(self):
        self.confirmar(tipo_entrega='mostrador')
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.costo_domicilio, Decimal('0'))
        self.assertEqual(pedido.total, Decimal('20000'))

    def test_pantalla_del_operador_muestra_el_domicilio_de_la_direccion_principal(self):
        self.casa.is_default = True
        self.casa.save()
        resp = self.client.get(reverse('operador_armar_pedido'))
        self.assertEqual(resp.context['costo_domicilio'], Decimal('4000'))
        self.assertContains(resp, 'costos-direccion')
