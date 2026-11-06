from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from menu.models import Sede

User = get_user_model()


class OperadorBase(TestCase):
    def setUp(self):
        self.operador = User.objects.create_user('operador1', password='x', role='operador', phone='3009876543')
        self.ana = User.objects.create_user('ana', password='x', role='cliente', phone='3001234567', first_name='Ana')
        self.beto = User.objects.create_user('beto', password='x', role='cliente', phone='3007654321')
        self.inactivo = User.objects.create_user('anita', password='x', role='cliente', phone='3000000000', is_active=False)
        self.cocina = User.objects.create_user('anacocina', password='x', role='cocina')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        self.otra = Sede.objects.create(name='Norte', address='Av 3')
        self.client.force_login(self.operador)
        self.url = reverse('operador_elegir_cliente')


class ElegirClienteTests(OperadorBase):  # HU15 · paso 2
    def test_sin_sede_muestra_las_sedes_para_elegir(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context['sede'])
        self.assertEqual(len(r.context['sedes']), 2)

    def test_elegir_sede_con_parametro_y_recordarla(self):
        r = self.client.get(self.url + f'?sede={self.sede.id}')
        self.assertEqual(r.context['sede'], self.sede)
        r = self.client.get(self.url)  # sin parámetro: la recuerda
        self.assertEqual(r.context['sede'], self.sede)

    def test_cambiar_sede(self):
        self.client.get(self.url + f'?sede={self.sede.id}')
        r = self.client.get(self.url + '?cambiar_sede=1')
        self.assertIsNone(r.context['sede'])

    def test_sede_invalida_se_ignora(self):
        r = self.client.get(self.url + '?sede=abc')
        self.assertIsNone(r.context['sede'])
        r = self.client.get(self.url + '?sede=9999')
        self.assertIsNone(r.context['sede'])

    def test_sede_inactiva_no_se_puede_elegir(self):
        Sede.objects.filter(pk=self.sede.pk).update(is_active=False)
        r = self.client.get(self.url + f'?sede={self.sede.id}')
        self.assertIsNone(r.context['sede'])

    def test_busca_cliente_por_usuario(self):
        r = self.client.get(self.url + f'?sede={self.sede.id}&q=ana')
        self.assertEqual(r.context['resultados'], [self.ana])

    def test_busca_cliente_por_telefono(self):
        r = self.client.get(self.url + f'?sede={self.sede.id}&q=3007654')
        self.assertEqual(r.context['resultados'], [self.beto])

    def test_la_busqueda_solo_trae_clientes_activos(self):
        r = self.client.get(self.url + f'?sede={self.sede.id}&q=ana')
        self.assertNotIn(self.cocina, r.context['resultados'])
        self.assertNotIn(self.inactivo, r.context['resultados'])

    def test_busqueda_sin_resultados(self):
        r = self.client.get(self.url + f'?sede={self.sede.id}&q=zzzz')
        self.assertEqual(r.context['resultados'], [])
        self.assertContains(r, 'No encontramos clientes')

    def test_seleccionar_cliente_lo_guarda_en_la_sesion(self):
        self.client.get(self.url + f'?sede={self.sede.id}')
        r = self.client.post(reverse('operador_seleccionar_cliente'), {'cliente_id': self.ana.id})
        self.assertRedirects(r, self.url)
        self.assertEqual(self.client.session['operador_cliente_id'], self.ana.id)

    def test_seleccionar_cliente_vacia_el_carrito_anterior(self):
        self.client.get(self.url + f'?sede={self.sede.id}')
        sesion = self.client.session
        sesion['carrito'] = {'sede_id': self.sede.id, 'items': {'1': 2}}
        sesion.save()
        self.client.post(reverse('operador_seleccionar_cliente'), {'cliente_id': self.ana.id})
        self.assertNotIn('carrito', self.client.session)

    def test_no_se_puede_seleccionar_a_un_no_cliente(self):
        self.client.get(self.url + f'?sede={self.sede.id}')
        r = self.client.post(reverse('operador_seleccionar_cliente'), {'cliente_id': self.cocina.id})
        self.assertEqual(r.status_code, 404)
        self.assertNotIn('operador_cliente_id', self.client.session)

    def test_seleccionar_sin_sede_no_hace_nada(self):
        r = self.client.post(reverse('operador_seleccionar_cliente'), {'cliente_id': self.ana.id})
        self.assertRedirects(r, self.url)
        self.assertNotIn('operador_cliente_id', self.client.session)

    def test_seleccionar_solo_acepta_post(self):
        self.assertEqual(self.client.get(reverse('operador_seleccionar_cliente')).status_code, 405)

    def test_cliente_recibe_403(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        r = self.client.post(reverse('operador_seleccionar_cliente'), {'cliente_id': self.beto.id})
        self.assertEqual(r.status_code, 403)

    def test_cocina_recibe_403(self):
        self.client.force_login(self.cocina)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonimo_va_al_login(self):
        self.client.logout()
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)