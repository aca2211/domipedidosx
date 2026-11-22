from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, ProductOption, Sede, SedeProduct


class OpcionesBase(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        cat = Category.objects.create(name='Comidas')
        self.burger = Product.objects.create(category=cat, name='Burger', description='d', price=Decimal('15000'))
        SedeProduct.objects.create(sede=self.sede, product=self.burger)


class ProductOptionModelTests(OpcionesBase):  # HU10
    def test_tipos_y_recargo_por_defecto(self):
        o = ProductOption.objects.create(product=self.burger, kind=ProductOption.SIZE, name='Grande')
        self.assertEqual(o.extra_price, 0)
        self.assertTrue(o.is_active)
        self.assertIn('Tamaño', str(o))

    def test_exclusion_no_puede_tener_recargo(self):
        o = ProductOption(product=self.burger, kind=ProductOption.EXCLUSION, name='Cebolla', extra_price=Decimal('500'))
        with self.assertRaises(ValidationError):
            o.full_clean()

    def test_recargo_negativo_es_invalido(self):
        o = ProductOption(product=self.burger, kind=ProductOption.ADDON, name='Queso', extra_price=Decimal('-1'))
        with self.assertRaises(ValidationError):
            o.full_clean()

    def test_no_se_repite_el_nombre_dentro_del_mismo_tipo(self):
        ProductOption.objects.create(product=self.burger, kind=ProductOption.ADDON, name='Queso')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductOption.objects.create(product=self.burger, kind=ProductOption.ADDON, name='Queso')

    def test_mismo_nombre_en_otro_tipo_es_valido(self):
        ProductOption.objects.create(product=self.burger, kind=ProductOption.ADDON, name='Tomate')
        ProductOption.objects.create(product=self.burger, kind=ProductOption.EXCLUSION, name='Tomate')
        self.assertEqual(self.burger.options.count(), 2)


class MenuMuestraOpcionesTests(OpcionesBase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model
        self.cliente = get_user_model().objects.create_user('ana', password='x', role='cliente')
        self.client.force_login(self.cliente)
        ProductOption.objects.create(product=self.burger, kind=ProductOption.SIZE, name='Normal')
        ProductOption.objects.create(product=self.burger, kind=ProductOption.SIZE, name='Grande', extra_price=Decimal('4000'))
        ProductOption.objects.create(product=self.burger, kind=ProductOption.ADDON, name='Tocineta', extra_price=Decimal('3000'))
        ProductOption.objects.create(product=self.burger, kind=ProductOption.EXCLUSION, name='Cebolla')
        ProductOption.objects.create(product=self.burger, kind=ProductOption.ADDON, name='Oculta', is_active=False)

    def test_el_menu_muestra_las_opciones_activas_agrupadas(self):
        r = self.client.get(reverse('menu_list'))
        self.assertContains(r, 'Personalizar')
        self.assertContains(r, 'Grande')
        self.assertContains(r, '(+$4000)')
        self.assertContains(r, 'Tocineta')
        self.assertContains(r, 'Sin Cebolla')
        self.assertNotContains(r, 'Oculta')

    def test_producto_sin_opciones_no_muestra_personalizar(self):
        self.burger.options.all().delete()
        self.assertNotContains(self.client.get(reverse('menu_list')), 'Personalizar')
