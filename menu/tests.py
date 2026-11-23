import shutil
import tempfile
from datetime import time
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, Product, Sede, SedeProduct


def imagen_de_prueba():
    buffer = BytesIO()
    Image.new('RGB', (10, 10), 'red').save(buffer, format='PNG')
    return SimpleUploadedFile('plato.png', buffer.getvalue(), content_type='image/png')


class SedeHorarioTests(TestCase):
    def test_horario_normal(self):
        sede = Sede(name='Centro', address='Cra 1', opening_time=time(10, 0), closing_time=time(22, 0))
        self.assertTrue(sede.is_open_at(time(12, 0)))
        self.assertTrue(sede.is_open_at(time(10, 0)))
        self.assertFalse(sede.is_open_at(time(22, 0)))
        self.assertFalse(sede.is_open_at(time(8, 0)))

    def test_horario_que_cruza_medianoche(self):
        sede = Sede(name='Nocturna', address='Cra 2', opening_time=time(18, 0), closing_time=time(2, 0))
        self.assertTrue(sede.is_open_at(time(23, 30)))
        self.assertTrue(sede.is_open_at(time(1, 0)))
        self.assertFalse(sede.is_open_at(time(12, 0)))

    def test_horario_por_defecto(self):
        sede = Sede.objects.create(name='Norte', address='Av 3')
        self.assertEqual(sede.opening_time, time(10, 0))
        self.assertEqual(sede.closing_time, time(22, 0))


class ProductoTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Hamburguesas')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')

    def crear(self, **extra):
        datos = dict(category=self.cat, name='Doble carne', description='Con queso', price='18000')
        datos.update(extra)
        p = Product.objects.create(**datos)
        SedeProduct.objects.create(sede=self.sede, product=p)
        return p

    def test_tiempo_de_preparacion_por_defecto(self):
        self.assertEqual(self.crear().prep_time_minutes, 15)

    def test_tiempo_de_preparacion_debe_ser_positivo(self):
        with self.assertRaises(ValidationError):
            self.crear(prep_time_minutes=0).full_clean()

    def test_imagen_es_opcional(self):
        self.crear().full_clean()


class MenuPublicoTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Bebidas')
        self.centro = Sede.objects.create(name='Centro', address='Cra 1')
        self.norte = Sede.objects.create(name='Norte', address='Av 3')
        self.jugo = self.producto('Jugo', 'Natural', '6000')
        self.cola = self.producto('Gaseosa', 'Fría', '4000')
        self.limonada = self.producto('Limonada', 'Agotada', '5000')
        SedeProduct.objects.create(sede=self.centro, product=self.jugo)
        SedeProduct.objects.create(sede=self.norte, product=self.cola)
        SedeProduct.objects.create(sede=self.centro, product=self.limonada, is_available=False)

    def producto(self, name, description, price):
        return Product.objects.create(category=self.cat, name=name, description=description, price=price)

    def test_menu_es_publico_y_oculta_no_disponibles(self):
        resp = self.client.get(reverse('menu_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Jugo')
        self.assertContains(resp, 'Gaseosa')
        self.assertNotContains(resp, 'Limonada')

    def test_filtro_por_sede(self):
        resp = self.client.get(reverse('menu_list'), {'sede': self.centro.id})
        self.assertContains(resp, 'Jugo')
        self.assertNotContains(resp, 'Gaseosa')

    def test_disponibilidad_es_por_sede(self):
        # El jugo se agota en Centro pero sigue disponible en Norte.
        SedeProduct.objects.filter(sede=self.centro, product=self.jugo).update(is_available=False)
        SedeProduct.objects.create(sede=self.norte, product=self.jugo)
        en_centro = self.client.get(reverse('menu_list'), {'sede': self.centro.id})
        en_norte = self.client.get(reverse('menu_list'), {'sede': self.norte.id})
        self.assertNotContains(en_centro, 'Jugo')
        self.assertContains(en_norte, 'Jugo')

    def test_producto_sin_sedes_no_aparece(self):
        self.producto('Fantasma', 'Sin sede', '1000')
        self.assertNotContains(self.client.get(reverse('menu_list')), 'Fantasma')

    def test_sede_inactiva_no_muestra_sus_productos(self):
        self.norte.is_active = False
        self.norte.save()
        self.assertNotContains(self.client.get(reverse('menu_list')), 'Gaseosa')

    def test_sede_invalida_en_filtro_no_rompe(self):
        resp = self.client.get(reverse('menu_list'), {'sede': 'abc'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Jugo')

    def test_pareja_sede_producto_es_unica(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SedeProduct.objects.create(sede=self.centro, product=self.jugo)

    def test_menu_muestra_tiempo_de_preparacion(self):
        self.assertContains(self.client.get(reverse('menu_list')), '15 min')

    def test_menu_muestra_imagen_del_producto(self):
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        with override_settings(MEDIA_ROOT=carpeta):
            self.jugo.image = imagen_de_prueba()
            self.jugo.save()
            resp = self.client.get(reverse('menu_list'))
            self.assertContains(resp, 'card-img-top')
            self.assertContains(resp, self.jugo.image.url)


from datetime import datetime as _datetime
from decimal import Decimal as _Decimal

from django.db import IntegrityError as _IntegrityError
from django.test import TestCase as _TestCase
from django.utils import timezone as _timezone

from menu.models import Feriado as _Feriado, ParametrosGlobales as _Parametros, Sede as _Sede


class FeriadoTests(_TestCase):
    """HU38: la sede no atiende en feriados."""

    def setUp(self):
        self.sede = _Sede.objects.create(name='Sede Centro', address='Calle 1')
        self.navidad = _timezone.make_aware(_datetime(2026, 12, 25, 12, 0))
        self.dia_normal = _timezone.make_aware(_datetime(2026, 12, 26, 12, 0))

    def test_sin_feriado_abre_en_horario(self):
        self.assertTrue(self.sede.is_open_at_datetime(self.navidad))

    def test_feriado_cierra_la_sede(self):
        _Feriado.objects.create(date=self.navidad.date(), name='Navidad')
        self.assertFalse(self.sede.is_open_at_datetime(self.navidad))

    def test_feriado_no_afecta_otros_dias(self):
        _Feriado.objects.create(date=self.navidad.date(), name='Navidad')
        self.assertTrue(self.sede.is_open_at_datetime(self.dia_normal))

    def test_dia_normal_fuera_de_horario_sigue_cerrado(self):
        madrugada = _timezone.make_aware(_datetime(2026, 12, 26, 6, 0))
        self.assertFalse(self.sede.is_open_at_datetime(madrugada))

    def test_fecha_unica(self):
        _Feriado.objects.create(date=self.navidad.date(), name='Navidad')
        with self.assertRaises(_IntegrityError):
            _Feriado.objects.create(date=self.navidad.date(), name='Otro')


class ParametrosGlobalesTests(_TestCase):
    """HU38: parámetros globales de una sola fila."""

    def test_cargar_crea_con_valores_por_defecto(self):
        p = _Parametros.cargar()
        self.assertEqual(p.margen_entrega_minutos, 10)
        self.assertEqual(p.pedido_minimo_global, _Decimal('0'))

    def test_cargar_devuelve_siempre_la_misma_fila(self):
        a = _Parametros.cargar()
        a.margen_entrega_minutos = 25
        a.save()
        self.assertEqual(_Parametros.cargar().margen_entrega_minutos, 25)
        self.assertEqual(_Parametros.objects.count(), 1)

    def test_no_permite_una_segunda_fila(self):
        _Parametros.cargar()
        _Parametros(margen_entrega_minutos=5).save()
        self.assertEqual(_Parametros.objects.count(), 1)
        self.assertEqual(_Parametros.cargar().margen_entrega_minutos, 5)
