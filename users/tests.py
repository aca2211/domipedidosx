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


# ---------- Operador en el admin del menú (HU04, HU11) ----------
from menu.models import Category, Product, Sede, SedeProduct


class AccesoOperadorTests(TestCase):
    def setUp(self):
        self.centro = Sede.objects.create(name='Centro', address='Cra 1')
        self.norte = Sede.objects.create(name='Norte', address='Cra 2')
        cat = Category.objects.create(name='Platos')
        self.burger = Product.objects.create(category=cat, name='Hamburguesa', description='x', price=10000)
        self.pizza = Product.objects.create(category=cat, name='Pizza', description='x', price=20000)
        self.sp_centro = SedeProduct.objects.create(sede=self.centro, product=self.burger)
        self.sp_norte = SedeProduct.objects.create(sede=self.norte, product=self.pizza)
        self.op = CustomUser.objects.create_user(
            'oscar', 'o@test.com', 'ClaveSegura#2026', role='operador', sede=self.centro)
        self.client.force_login(self.op)

    def test_ve_solo_los_productos_de_su_sede_en_sedeproduct(self):
        r = self.client.get(reverse('admin:menu_sedeproduct_changelist'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Hamburguesa')
        self.assertNotContains(r, 'Pizza')

    def test_ve_solo_los_productos_de_su_sede_en_productos(self):
        r = self.client.get(reverse('admin:menu_product_changelist'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Hamburguesa')
        self.assertNotContains(r, 'Pizza')

    def test_no_abre_registros_de_otra_sede(self):
        r = self.client.get(reverse('admin:menu_sedeproduct_change', args=[self.sp_norte.pk]))
        self.assertEqual(r.status_code, 302)

    def test_cambia_la_disponibilidad_de_su_sede(self):
        r = self.client.post(reverse('admin:menu_sedeproduct_change', args=[self.sp_centro.pk]), {})
        self.assertEqual(r.status_code, 302)
        self.sp_centro.refresh_from_db()
        self.assertFalse(self.sp_centro.is_available)

    def test_no_modifica_la_disponibilidad_de_otra_sede(self):
        self.client.post(reverse('admin:menu_sedeproduct_change', args=[self.sp_norte.pk]), {})
        self.sp_norte.refresh_from_db()
        self.assertTrue(self.sp_norte.is_available)

    def test_no_puede_borrar(self):
        r = self.client.get(reverse('admin:menu_sedeproduct_delete', args=[self.sp_centro.pk]))
        self.assertEqual(r.status_code, 403)

    def test_no_edita_productos(self):
        self.client.post(reverse('admin:menu_product_change', args=[self.burger.pk]), {
            'category': self.burger.category_id, 'name': 'Cambiado',
            'description': 'x', 'price': '1', 'prep_time_minutes': 15,
        })
        self.burger.refresh_from_db()
        self.assertEqual(self.burger.name, 'Hamburguesa')

    def test_no_entra_a_usuarios(self):
        r = self.client.get(reverse('admin:users_customuser_changelist'))
        self.assertEqual(r.status_code, 403)

    def test_agrega_productos_solo_a_su_sede(self):
        url = reverse('admin:menu_sedeproduct_add')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Norte')
        # intentar otra sede no es válido
        self.client.post(url, {'sede': self.norte.pk, 'product': self.burger.pk, 'is_available': 'on'})
        self.assertEqual(SedeProduct.objects.count(), 2)
        # su sede sí
        r = self.client.post(url, {'sede': self.centro.pk, 'product': self.pizza.pk, 'is_available': 'on'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(SedeProduct.objects.filter(sede=self.centro, product=self.pizza).exists())

    def test_operador_sin_sede_no_ve_registros(self):
        sin = CustomUser.objects.create_user('sinsede', 's@test.com', 'ClaveSegura#2026', role='operador')
        self.client.force_login(sin)
        r = self.client.get(reverse('admin:menu_sedeproduct_changelist'))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Hamburguesa')

    def test_cliente_no_entra_al_admin(self):
        cli = CustomUser.objects.create_user('cli', 'c@test.com', 'ClaveSegura#2026')
        self.client.force_login(cli)
        r = self.client.get(reverse('admin:menu_sedeproduct_changelist'))
        self.assertEqual(r.status_code, 302)


# ---------- Perfil y direcciones del cliente (HU05) ----------
class PerfilYDireccionesTests(TestCase):
    def setUp(self):
        self.cliente = CustomUser.objects.create_user(
            'andrea', 'andrea@test.com', 'ClaveSegura#2026',
            first_name='Andrea', last_name='Pérez', phone='3001234567')
        self.otro = CustomUser.objects.create_user(
            'beto', 'beto@test.com', 'ClaveSegura#2026', phone='3009998888')
        self.client.force_login(self.cliente)

    def datos_perfil(self, **extra):
        datos = {'first_name': 'Andrea', 'last_name': 'Pérez',
                 'email': 'andrea@test.com', 'phone': '3001234567'}
        datos.update(extra)
        return datos

    def datos_direccion(self, **extra):
        datos = {'label': 'Casa', 'address': 'Calle 5 # 38-10', 'details': ''}
        datos.update(extra)
        return datos

    # --- perfil ---
    def test_perfil_muestra_los_datos(self):
        r = self.client.get(reverse('perfil'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'andrea@test.com')

    def test_perfil_actualiza_los_datos(self):
        r = self.client.post(reverse('perfil'), self.datos_perfil(
            first_name='Ana', email='NUEVO@Test.com', phone='300 111 2222'))
        self.assertRedirects(r, reverse('perfil'))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.first_name, 'Ana')
        self.assertEqual(self.cliente.email, 'nuevo@test.com')
        self.assertEqual(self.cliente.phone, '3001112222')

    def test_perfil_rechaza_correo_de_otro_usuario(self):
        r = self.client.post(reverse('perfil'), self.datos_perfil(email='BETO@test.com'))
        self.assertEqual(r.status_code, 200)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.email, 'andrea@test.com')

    def test_perfil_permite_conservar_el_propio_correo(self):
        r = self.client.post(reverse('perfil'), self.datos_perfil(first_name='Andrea María'))
        self.assertRedirects(r, reverse('perfil'))

    def test_perfil_rechaza_telefono_invalido(self):
        r = self.client.post(reverse('perfil'), self.datos_perfil(phone='abc'))
        self.assertEqual(r.status_code, 200)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.phone, '3001234567')

    def test_perfil_no_permite_cambiar_el_rol(self):
        self.client.post(reverse('perfil'), self.datos_perfil(role='admin'))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.role, 'cliente')
        self.assertFalse(self.cliente.is_staff)

    def test_anonimo_va_al_login(self):
        self.client.logout()
        for nombre in ('perfil', 'direccion_lista', 'direccion_crear'):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertIn('/login/', r.url)

    def test_otros_roles_no_entran_al_perfil_ni_a_direcciones(self):
        cocina = CustomUser.objects.create_user('chef', 'chef@test.com', 'ClaveSegura#2026', role='repartidor')
        self.client.force_login(cocina)
        for nombre in ('perfil', 'direccion_lista', 'direccion_crear'):
            r = self.client.get(reverse(nombre))
            self.assertRedirects(r, reverse('home'), fetch_redirect_response=False)

    # --- direcciones ---
    def test_la_url_que_espera_pedidos_existe(self):
        self.assertEqual(reverse('direccion_crear'), '/direcciones/nueva/')

    def test_la_primera_direccion_queda_como_principal(self):
        r = self.client.post(reverse('direccion_crear'), self.datos_direccion())
        self.assertRedirects(r, reverse('direccion_lista'))
        d = self.cliente.direcciones.get()
        self.assertTrue(d.is_default)
        self.assertEqual(d.user, self.cliente)

    def test_la_segunda_no_quita_la_principal(self):
        self.client.post(reverse('direccion_crear'), self.datos_direccion())
        self.client.post(reverse('direccion_crear'), self.datos_direccion(label='Trabajo', address='Av. 6N # 25-30'))
        self.assertEqual(self.cliente.direcciones.count(), 2)
        self.assertEqual(self.cliente.direcciones.get(is_default=True).label, 'Casa')

    def test_marcar_como_principal_al_crear(self):
        self.client.post(reverse('direccion_crear'), self.datos_direccion())
        self.client.post(reverse('direccion_crear'), self.datos_direccion(
            label='Trabajo', address='Av. 6N # 25-30', is_default='on'))
        self.assertEqual(self.cliente.direcciones.get(is_default=True).label, 'Trabajo')

    def test_hacer_principal(self):
        Direccion.objects.create(user=self.cliente, label='Casa', address='Calle 1', is_default=True)
        otra = Direccion.objects.create(user=self.cliente, label='Trabajo', address='Calle 2')
        r = self.client.post(reverse('direccion_principal', args=[otra.pk]))
        self.assertRedirects(r, reverse('direccion_lista'))
        self.assertEqual(self.cliente.direcciones.get(is_default=True), otra)

    def test_editar_direccion_propia(self):
        d = Direccion.objects.create(user=self.cliente, label='Casa', address='Calle 1', is_default=True)
        r = self.client.post(reverse('direccion_editar', args=[d.pk]), self.datos_direccion(
            label='Casa nueva', address='Calle 9 # 9-9', is_default='on'))
        self.assertRedirects(r, reverse('direccion_lista'))
        d.refresh_from_db()
        self.assertEqual((d.label, d.address), ('Casa nueva', 'Calle 9 # 9-9'))

    def test_editar_no_deja_al_cliente_sin_principal(self):
        d = Direccion.objects.create(user=self.cliente, label='Casa', address='Calle 1', is_default=True)
        self.client.post(reverse('direccion_editar', args=[d.pk]), self.datos_direccion(label='Casa'))
        d.refresh_from_db()
        self.assertTrue(d.is_default)

    def test_no_edita_direccion_ajena(self):
        ajena = Direccion.objects.create(user=self.otro, label='Casa', address='Otra calle 1')
        r = self.client.post(reverse('direccion_editar', args=[ajena.pk]), self.datos_direccion(label='Hack'))
        self.assertEqual(r.status_code, 404)
        ajena.refresh_from_db()
        self.assertEqual(ajena.label, 'Casa')

    def test_eliminar_direccion_propia(self):
        d = Direccion.objects.create(user=self.cliente, label='Casa', address='Calle 1', is_default=True)
        r = self.client.post(reverse('direccion_eliminar', args=[d.pk]))
        self.assertRedirects(r, reverse('direccion_lista'))
        self.assertFalse(self.cliente.direcciones.exists())

    def test_eliminar_exige_post(self):
        d = Direccion.objects.create(user=self.cliente, label='Casa', address='Calle 1')
        r = self.client.get(reverse('direccion_eliminar', args=[d.pk]))
        self.assertEqual(r.status_code, 405)
        self.assertTrue(self.cliente.direcciones.exists())

    def test_eliminar_la_principal_promueve_otra(self):
        principal = Direccion.objects.create(user=self.cliente, label='Casa', address='Calle 1', is_default=True)
        otra = Direccion.objects.create(user=self.cliente, label='Trabajo', address='Calle 2')
        self.client.post(reverse('direccion_eliminar', args=[principal.pk]))
        otra.refresh_from_db()
        self.assertTrue(otra.is_default)

    def test_no_elimina_ni_cambia_direccion_ajena(self):
        ajena = Direccion.objects.create(user=self.otro, label='Casa', address='Otra calle 1')
        self.assertEqual(self.client.post(reverse('direccion_eliminar', args=[ajena.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('direccion_principal', args=[ajena.pk])).status_code, 404)
        self.assertTrue(Direccion.objects.filter(pk=ajena.pk).exists())

    def test_la_lista_solo_muestra_las_propias(self):
        Direccion.objects.create(user=self.cliente, label='Mi casa', address='Calle 1')
        Direccion.objects.create(user=self.otro, label='Casa de Beto', address='Calle 2')
        r = self.client.get(reverse('direccion_lista'))
        self.assertContains(r, 'Mi casa')
        self.assertNotContains(r, 'Casa de Beto')

    def test_next_interno_se_respeta(self):
        r = self.client.post(reverse('direccion_crear'), self.datos_direccion(next=reverse('perfil')))
        self.assertRedirects(r, reverse('perfil'))

    def test_next_externo_se_ignora(self):
        r = self.client.post(reverse('direccion_crear'), self.datos_direccion(next='https://evil.example.com/'))
        self.assertRedirects(r, reverse('direccion_lista'))
