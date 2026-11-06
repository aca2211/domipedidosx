from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Direccion


class DireccionInline(admin.TabularInline):
    model = Direccion
    extra = 0


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'phone', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = UserAdmin.search_fields + ('phone',)
    fieldsets = UserAdmin.fieldsets + (('Rol en DomiPedidosX', {'fields': ('role', 'phone')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rol en DomiPedidosX', {'fields': ('email', 'phone', 'role')}),
    )
    inlines = [DireccionInline]
