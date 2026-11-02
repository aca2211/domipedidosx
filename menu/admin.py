from django.contrib import admin
from .models import Sede, Category, Product

@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'is_active')
    list_filter = ('is_active',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_available')
    list_filter = ('category', 'sede', 'is_available')
    search_fields = ('name',)

admin.site.site_header = 'DomiPedidosX · Administración'
admin.site.site_title = 'DomiPedidosX'
admin.site.index_title = 'Panel de administración'
