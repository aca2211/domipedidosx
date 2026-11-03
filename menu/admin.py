from django.contrib import admin
from .models import Sede, Category, Product, SedeProduct

@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'opening_time', 'closing_time', 'is_active')
    list_filter = ('is_active',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

class SedeProductInline(admin.TabularInline):
    model = SedeProduct
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'prep_time_minutes')
    list_filter = ('category', 'sedes')
    search_fields = ('name',)
    inlines = [SedeProductInline]

@admin.register(SedeProduct)
class SedeProductAdmin(admin.ModelAdmin):
    """Vista rápida para marcar disponible / no disponible por sede (HU11)."""
    list_display = ('product', 'sede', 'is_available')
    list_editable = ('is_available',)
    list_filter = ('sede', 'is_available')
    search_fields = ('product__name',)

admin.site.site_header = 'DomiPedidosX · Administración'
admin.site.site_title = 'DomiPedidosX'
admin.site.index_title = 'Panel de administración'
