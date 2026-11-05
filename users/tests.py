from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from .models import CustomUser, Direccion


def datos_registro(**extra):
    data = {
        'username': 'ana', 'first_name': 'Ana', 'last_name': 'Pérez',
        'email': 'ana@test.com', 'phone': '3001234567',
        'password1': 'ClaveSegura#2026', 'password2': 'ClaveSegura#2026',
    }
    data.update(extra)
    return data


class AuthTests(TestCase):
    def test_registro_crea_cliente(self):
        resp = self.client.post(reverse('register'), datos_registro())
        self.assertRedirects(resp, reverse('home'))
        user = CustomUser.objects.get(username='ana')
        self.assertEqual(user.role, 'cliente')
        self.assertEqual(user.phone, '3001234567')

    def test_registro_no_permite_elegir_rol(self):
        self.client.post(reverse('register'), datos_registro(username='hacker', email='h@test.com', role='admin'))
        self.assertEqual(CustomUser.objects.get(username='hacker').role, 'cliente')

    def test_registro_exige_telefono(self):
        resp = self.client.post(reverse('register'), datos_registro(phone=''))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(CustomUser.objects.filter(username='ana').exists())

    def test_registro_rechaza_telefono_invalido(self):
        resp = self.client.post(reverse('register'), datos_registro(phone='abc123'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(CustomUser.objects.filter(username='ana').exists())

    def test_registro_normaliza_telefono(self):
        self.client.post(reverse('register'), datos_registro(phone='300 123-4567'))
        self.assertEqual(CustomUser.objects.get(username='ana').phone, '3001234567')

    def test_login_y_logout(self):
        CustomUser.objects.create_user('luis', 'l@test.com', 'ClaveSegura#2026')
        self.assertTrue(self.client.login(username='luis', password='ClaveSegura#2026'))
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
        self.client.post(reverse('logout'))
        self.assertEqual(self.client.get(reverse('home')).status_code, 302)

    def test_home_requiere_login(self):
        self.assertEqual(self.client.get(reverse('home')).status_code, 302)


class DireccionTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user('ana', 'ana@test.com', 'ClaveSegura#2026')
        self.otro = CustomUser.objects.create_user('luis', 'l@test.com', 'ClaveSegura#2026')

    def test_usuario_puede_tener_varias_direcciones(self):
        Direccion.objects.create(user=self.user, label='Casa', address='Calle 5 # 38-10')
        Direccion.objects.create(user=self.user, label='Trabajo', address='Av. 6N # 25-30')
        self.assertEqual(self.user.direcciones.count(), 2)

    def test_nueva_principal_desmarca_la_anterior(self):
        casa = Direccion.objects.create(user=self.user, label='Casa', address='Calle 5 # 38-10', is_default=True)
        trabajo = Direccion.objects.create(user=self.user, label='Trabajo', address='Av. 6N # 25-30', is_default=True)
        casa.refresh_from_db()
        trabajo.refresh_from_db()
        self.assertFalse(casa.is_default)
        self.assertTrue(trabajo.is_default)

    def test_principal_de_un_usuario_no_afecta_a_otro(self):
        Direccion.objects.create(user=self.user, label='Casa', address='Calle 5 # 38-10', is_default=True)
        Direccion.objects.create(user=self.otro, label='Casa', address='Cra 1 # 2-3', is_default=True)
        self.assertEqual(Direccion.objects.filter(is_default=True).count(), 2)

    def test_restriccion_en_bd_impide_dos_principales(self):
        Direccion.objects.create(user=self.user, label='Casa', address='Calle 5 # 38-10', is_default=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Direccion.objects.bulk_create([
                Direccion(user=self.user, label='Otra', address='Cra 9 # 9-9', is_default=True)
            ])

    def test_direcciones_se_borran_con_el_usuario(self):
        Direccion.objects.create(user=self.user, label='Casa', address='Calle 5 # 38-10')
        self.user.delete()
        self.assertEqual(Direccion.objects.count(), 0)


# ---------- Sede del personal y acceso por rol (HU04) ----------
from django.core.exceptions import ValidationError


class RolYSedeTests(TestCase):
    def test_operador_queda_como_staff(self):
        u = CustomUser.objects.create_user('oscar', 'o@test.com', 'ClaveSegura#2026', role='operador')
        self.assertTrue(u.is_staff)
        self.assertFalse(u.is_superuser)

    def test_admin_queda_como_superusuario(self):
        u = CustomUser.objects.create_user('adm', 'a@test.com', 'ClaveSegura#2026', role='admin')
        self.assertTrue(u.is_staff)
        self.assertTrue(u.is_superuser)

    def test_cliente_cocina_y_repartidor_no_son_staff(self):
        for rol in ('cliente', 'cocina', 'repartidor'):
            u = CustomUser.objects.create_user(f'u_{rol}', f'{rol}@test.com', 'ClaveSegura#2026', role=rol)
            self.assertFalse(u.is_staff, rol)

    def test_operador_y_cocina_exigen_sede(self):
        for rol in ('operador', 'cocina'):
            with self.assertRaises(ValidationError) as cm:
                CustomUser(username='x', role=rol).clean()
            self.assertIn('sede', cm.exception.message_dict)

    def test_cliente_y_repartidor_no_exigen_sede(self):
        for rol in ('cliente', 'repartidor'):
            CustomUser(username='x', role=rol).clean()

    def test_usuario_con_sede(self):
        from menu.models import Sede
        sede = Sede.objects.create(name='Centro', address='Cra 1')
        u = CustomUser.objects.create_user('oscar', 'o@test.com', 'ClaveSegura#2026', role='operador', sede=sede)
        u.clean()
        self.assertEqual(list(sede.personal.all()), [u])
