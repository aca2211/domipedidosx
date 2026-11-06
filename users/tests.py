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


# ---------- Recuperar contraseña (HU03) ----------
import re
from urllib.parse import urlparse

from django.core import mail


class RecuperarContrasenaTests(TestCase):
    CLAVE_VIEJA = 'ClaveVieja#2026'
    CLAVE_NUEVA = 'ClaveNueva#2026'

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            'ana', email='ana@test.com', password=self.CLAVE_VIEJA, role='cliente', phone='3001234567')

    def _pedir(self, email='ana@test.com'):
        return self.client.post(reverse('password_reset'), {'email': email})

    def _ruta_del_enlace(self):
        cuerpo = mail.outbox[0].body
        url = re.search(r'https?://\S+/recuperar/\S+/', cuerpo).group(0)
        return urlparse(url).path

    def test_login_tiene_enlace_de_recuperacion(self):
        resp = self.client.get(reverse('login'))
        self.assertContains(resp, reverse('password_reset'))
        self.assertContains(resp, '¿Olvidaste tu contraseña?')

    def test_formulario_carga(self):
        self.assertEqual(self.client.get(reverse('password_reset')).status_code, 200)

    def test_envia_correo_a_cuenta_activa(self):
        resp = self._pedir()
        self.assertRedirects(resp, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana@test.com'])
        self.assertIn('Recuperación', mail.outbox[0].subject)
        self.assertIn('ana', mail.outbox[0].body)

    def test_correo_no_distingue_mayusculas(self):
        self._pedir('ANA@Test.com')
        self.assertEqual(len(mail.outbox), 1)

    def test_correo_inexistente_no_revela_nada(self):
        resp = self._pedir('nadie@test.com')
        self.assertRedirects(resp, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_usuario_inactivo_no_recibe_correo(self):
        self.user.is_active = False
        self.user.save()
        self._pedir()
        self.assertEqual(len(mail.outbox), 0)

    def test_correo_vacio_es_invalido(self):
        resp = self._pedir('')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_flujo_completo_cambia_la_contrasena(self):
        self._pedir()
        ruta = self._ruta_del_enlace()
        paso = self.client.get(ruta)
        self.assertEqual(paso.status_code, 302)   # Django guarda el token en sesión y redirige
        resp = self.client.post(paso.url, {
            'new_password1': self.CLAVE_NUEVA, 'new_password2': self.CLAVE_NUEVA})
        self.assertRedirects(resp, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.CLAVE_NUEVA))
        self.assertFalse(self.user.check_password(self.CLAVE_VIEJA))
        self.client.logout()
        self.assertTrue(self.client.login(username='ana', password=self.CLAVE_NUEVA))

    def test_enlace_es_de_un_solo_uso(self):
        self._pedir()
        ruta = self._ruta_del_enlace()
        paso = self.client.get(ruta)
        self.client.post(paso.url, {
            'new_password1': self.CLAVE_NUEVA, 'new_password2': self.CLAVE_NUEVA})
        resp = self.client.get(ruta)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['validlink'])

    def test_enlace_alterado_no_es_valido(self):
        resp = self.client.get(reverse('password_reset_confirm', args=['abc', 'token-falso']))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['validlink'])

    def test_contrasena_debil_se_rechaza(self):
        self._pedir()
        paso = self.client.get(self._ruta_del_enlace())
        resp = self.client.post(paso.url, {'new_password1': '123', 'new_password2': '123'})
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.CLAVE_VIEJA))


# ---------- Desactivar clientes (HU06) ----------
from menu.models import Sede


class DesactivarUsuariosTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            'jefe', password='ClaveAdmin#2026', role='admin', email='jefe@test.com')
        self.cliente = CustomUser.objects.create_user(
            'ana', password='ClaveSegura#2026', role='cliente', phone='3001234567')
        self.otro = CustomUser.objects.create_user(
            'beto', password='ClaveSegura#2026', role='cliente', phone='3007654321')
        self.url = reverse('admin:users_customuser_changelist')
        self.client.force_login(self.admin_user)

    def _accion(self, nombre, *usuarios):
        return self.client.post(self.url, {
            'action': nombre,
            '_selected_action': [u.pk for u in usuarios],
        }, follow=True)

    def test_admin_desactiva_clientes_seleccionados(self):
        resp = self._accion('desactivar_usuarios', self.cliente, self.otro)
        self.assertContains(resp, 'Usuarios desactivados: 2.')
        self.cliente.refresh_from_db()
        self.otro.refresh_from_db()
        self.assertFalse(self.cliente.is_active)
        self.assertFalse(self.otro.is_active)

    def test_admin_activa_clientes_desactivados(self):
        CustomUser.objects.filter(pk=self.cliente.pk).update(is_active=False)
        resp = self._accion('activar_usuarios', self.cliente)
        self.assertContains(resp, 'Usuarios activados: 1.')
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.is_active)

    def test_no_puede_desactivarse_a_si_mismo(self):
        resp = self._accion('desactivar_usuarios', self.admin_user, self.cliente)
        self.assertContains(resp, 'No puedes desactivar tu propia cuenta.')
        self.admin_user.refresh_from_db()
        self.cliente.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)
        self.assertFalse(self.cliente.is_active)

    def test_las_acciones_aparecen_en_el_listado(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, 'Desactivar usuarios seleccionados')
        self.assertContains(resp, 'Activar usuarios seleccionados')

    def test_usuario_inactivo_no_puede_iniciar_sesion(self):
        self._accion('desactivar_usuarios', self.cliente)
        self.client.logout()
        resp = self.client.post(reverse('login'), {'username': 'ana', 'password': 'ClaveSegura#2026'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_usuario_inactivo_pierde_la_sesion_abierta(self):
        otro_navegador = self.client_class()
        self.assertTrue(otro_navegador.login(username='ana', password='ClaveSegura#2026'))
        self.assertEqual(otro_navegador.get(reverse('home')).status_code, 200)
        self._accion('desactivar_usuarios', self.cliente)
        resp = otro_navegador.get(reverse('home'))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('home')}")

    def test_usuario_desactivado_no_aparece_al_operador(self):
        sede = Sede.objects.create(name='Centro', address='Cra 1')
        operador = CustomUser.objects.create_user(
            'oper', password='x', role='operador', sede=sede)
        url = reverse('operador_elegir_cliente') + f'?sede={sede.id}&q=ana'
        self.client.force_login(operador)
        self.assertEqual(self.client.get(url).context['resultados'], [self.cliente])
        self.client.force_login(self.admin_user)
        self._accion('desactivar_usuarios', self.cliente)
        self.client.force_login(operador)
        self.assertEqual(self.client.get(url).context['resultados'], [])

    def test_operador_no_puede_usar_el_admin_de_usuarios(self):
        sede = Sede.objects.create(name='Centro', address='Cra 1')
        operador = CustomUser.objects.create_user('oper', password='x', role='operador', sede=sede)
        self.client.force_login(operador)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        resp = self.client.post(self.url, {
            'action': 'desactivar_usuarios', '_selected_action': [self.cliente.pk]})
        self.assertEqual(resp.status_code, 403)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.is_active)


# ---------- Roles desde el admin (HU04) ----------
class RolesDesdeAdminTests(TestCase):
    """Alta y cambio de roles desde el admin (HU04)."""

    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            'jefe', password='ClaveAdmin#2026', role='admin', email='jefe@test.com')
        self.sede = Sede.objects.create(name='Centro', address='Cra 1')
        self.client.force_login(self.admin_user)

    def _alta(self, **extra):
        data = {
            'username': 'nuevo', 'usable_password': 'true',
            'password1': 'ClaveNueva#2026', 'password2': 'ClaveNueva#2026',
            'email': 'nuevo@test.com', 'phone': '3001112222', 'role': 'cliente', 'sede': '',
            'direcciones-TOTAL_FORMS': '0', 'direcciones-INITIAL_FORMS': '0',
            'direcciones-MIN_NUM_FORMS': '0', 'direcciones-MAX_NUM_FORMS': '1000',
        }
        data.update(extra)
        return self.client.post(reverse('admin:users_customuser_add'), data)

    def _datos_cambio(self, **extra):
        data = {
            'username': 'ana', 'first_name': '', 'last_name': '', 'email': 'ana@test.com',
            'is_active': 'on', 'date_joined_0': '2026-01-01', 'date_joined_1': '00:00:00',
            'role': 'cliente', 'phone': '3001234567', 'sede': '',
            'direcciones-TOTAL_FORMS': '0', 'direcciones-INITIAL_FORMS': '0',
            'direcciones-MIN_NUM_FORMS': '0', 'direcciones-MAX_NUM_FORMS': '1000',
        }
        data.update(extra)
        return data

    def test_alta_de_operador_con_sede(self):
        resp = self._alta(role='operador', sede=self.sede.pk)
        self.assertEqual(resp.status_code, 302)
        u = CustomUser.objects.get(username='nuevo')
        self.assertEqual((u.role, u.sede), ('operador', self.sede))
        self.assertTrue(u.is_staff)
        self.assertFalse(u.is_superuser)

    def test_alta_de_operador_sin_sede_se_rechaza(self):
        resp = self._alta(role='operador')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(CustomUser.objects.filter(username='nuevo').exists())
        self.assertContains(resp, 'deben tener una sede asignada')

    def test_alta_de_cocina_sin_sede_se_rechaza(self):
        resp = self._alta(role='cocina')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(CustomUser.objects.filter(username='nuevo').exists())

    def test_alta_de_cocina_con_sede_no_entra_al_admin(self):
        self._alta(role='cocina', sede=self.sede.pk)
        u = CustomUser.objects.get(username='nuevo')
        self.assertEqual(u.role, 'cocina')
        self.assertFalse(u.is_staff)

    def test_alta_de_repartidor_y_cliente_sin_sede(self):
        self._alta(username='repa', email='r@test.com', role='repartidor')
        self._alta(username='clie', email='c@test.com', role='cliente')
        self.assertFalse(CustomUser.objects.get(username='repa').is_staff)
        self.assertFalse(CustomUser.objects.get(username='clie').is_staff)

    def test_alta_de_administrador_es_superusuario(self):
        self._alta(role='admin')
        u = CustomUser.objects.get(username='nuevo')
        self.assertTrue(u.is_staff)
        self.assertTrue(u.is_superuser)

    def test_cambiar_rol_de_cliente_a_operador(self):
        cliente = CustomUser.objects.create_user(
            'ana', password='x', role='cliente', phone='3001234567', email='ana@test.com')
        resp = self.client.post(
            reverse('admin:users_customuser_change', args=[cliente.pk]),
            self._datos_cambio(role='operador', sede=self.sede.pk))
        self.assertEqual(resp.status_code, 302)
        cliente.refresh_from_db()
        self.assertEqual((cliente.role, cliente.sede), ('operador', self.sede))
        self.assertTrue(cliente.is_staff)

    def test_cambiar_a_operador_sin_sede_se_rechaza(self):
        cliente = CustomUser.objects.create_user(
            'ana', password='x', role='cliente', phone='3001234567', email='ana@test.com')
        resp = self.client.post(
            reverse('admin:users_customuser_change', args=[cliente.pk]),
            self._datos_cambio(role='operador'))
        self.assertEqual(resp.status_code, 200)
        cliente.refresh_from_db()
        self.assertEqual(cliente.role, 'cliente')
