from django.test import TestCase
from django.urls import reverse
from .models import CustomUser

class AuthTests(TestCase):
    def test_registro_crea_cliente(self):
        data = {
            'username': 'ana', 'first_name': 'Ana', 'last_name': 'Pérez',
            'email': 'ana@test.com', 'password1': 'ClaveSegura#2026', 'password2': 'ClaveSegura#2026',
        }
        resp = self.client.post(reverse('register'), data)
        self.assertRedirects(resp, reverse('home'))
        self.assertEqual(CustomUser.objects.get(username='ana').role, 'cliente')

    def test_registro_no_permite_elegir_rol(self):
        data = {
            'username': 'hacker', 'first_name': 'H', 'last_name': 'X',
            'email': 'h@test.com', 'password1': 'ClaveSegura#2026', 'password2': 'ClaveSegura#2026',
            'role': 'admin',
        }
        self.client.post(reverse('register'), data)
        self.assertEqual(CustomUser.objects.get(username='hacker').role, 'cliente')

    def test_login_y_logout(self):
        CustomUser.objects.create_user('luis', 'l@test.com', 'ClaveSegura#2026')
        self.assertTrue(self.client.login(username='luis', password='ClaveSegura#2026'))
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
        self.client.post(reverse('logout'))
        self.assertEqual(self.client.get(reverse('home')).status_code, 302)

    def test_home_requiere_login(self):
        self.assertEqual(self.client.get(reverse('home')).status_code, 302)
