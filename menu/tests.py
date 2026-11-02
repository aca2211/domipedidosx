import shutil
import tempfile
from datetime import time
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, Product, Sede


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
        p.sede.add(self.sede)
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
        self.jugo = Product.objects.create(category=self.cat, name='Jugo', description='Natural', price='6000')
        self.jugo.sede.add(self.centro)
        self.cola = Product.objects.create(category=self.cat, name='Gaseosa', description='Fría', price='4000')
        self.cola.sede.add(self.norte)
        self.agotado = Product.objects.create(
            category=self.cat, name='Limonada', description='Agotada', price='5000', is_available=False)
        self.agotado.sede.add(self.centro)

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
