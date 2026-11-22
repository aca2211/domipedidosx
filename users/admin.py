from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Direccion


class DireccionInline(admin.TabularInline):
    model = Direccion
    extra = 0


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'phone', 'role', 'sede', 'is_active', 'is_staff')
    list_filter = ('role', 'sede', 'is_active', 'is_staff')
    search_fields = UserAdmin.search_fields + ('phone',)
    fieldsets = UserAdmin.fieldsets + (('Rol en DomiPedidosX', {'fields': ('role', 'phone', 'sede')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rol en DomiPedidosX', {'fields': ('email', 'phone', 'role', 'sede')}),
    )
    inlines = [DireccionInline]
    actions = ['activar_usuarios', 'desactivar_usuarios']

    @admin.action(description='Activar usuarios seleccionados', permissions=['change'])
    def activar_usuarios(self, request, queryset):
        cantidad = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f'Usuarios activados: {cantidad}.', messages.SUCCESS)

    @admin.action(description='Desactivar usuarios seleccionados', permissions=['change'])
    def desactivar_usuarios(self, request, queryset):
        # Un usuario inactivo no inicia sesión y pierde la sesión que tuviera abierta.
        # Nadie puede desactivarse a sí mismo (se quedaría sin acceso al admin).
        propio = queryset.filter(pk=request.user.pk).exists()
        cantidad = queryset.exclude(pk=request.user.pk).filter(is_active=True).update(is_active=False)
        self.message_user(request, f'Usuarios desactivados: {cantidad}.', messages.SUCCESS)
        if propio:
            self.message_user(request, 'No puedes desactivar tu propia cuenta.', messages.WARNING)
