from django.contrib import admin
from .models import Sede, Category, Product, SedeProduct


def es_operador(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'operador'


class OperadorAdminMixin:
    """Reglas del rol operador en el admin (HU04, HU11).

    El operador siempre puede ver; agregar y editar dependen de los atributos de la clase;
    nunca puede borrar. Para cualquier otro usuario se aplican los permisos normales de Django.
    `campo_sede` es la ruta ORM hacia la sede para filtrar lo que ve (None = sin filtro).
    """
    campo_sede = None
    operador_puede_agregar = False
    operador_puede_editar = False

    def has_module_permission(self, request):
        return es_operador(request.user) or super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return es_operador(request.user) or super().has_view_permission(request, obj)

    def has_add_permission(self, request, *args):
        if es_operador(request.user):
            return self.operador_puede_agregar
        return super().has_add_permission(request, *args)

    def has_change_permission(self, request, obj=None):
        if es_operador(request.user):
            return self.operador_puede_editar
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if es_operador(request.user):
            return False
        return super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if es_operador(request.user) and self.campo_sede:
            if not request.user.sede_id:
                return qs.none()
            qs = qs.filter(**{self.campo_sede: request.user.sede_id}).distinct()
        return qs


@admin.register(Sede)
class SedeAdmin(OperadorAdminMixin, admin.ModelAdmin):
    campo_sede = 'pk'
    list_display = ('name', 'address', 'opening_time', 'closing_time', 'is_active')
    list_filter = ('is_active',)


@admin.register(Category)
class CategoryAdmin(OperadorAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'description')


class SedeProductInline(admin.TabularInline):
    model = SedeProduct
    extra = 1


@admin.register(Product)
class ProductAdmin(OperadorAdminMixin, admin.ModelAdmin):
    campo_sede = 'sedes'
    list_display = ('name', 'category', 'price', 'prep_time_minutes')
    list_filter = ('category', 'sedes')
    search_fields = ('name',)
    inlines = [SedeProductInline]

    def get_inlines(self, request, obj):
        if es_operador(request.user):
            return []   # el inline mostraría las demás sedes
        return super().get_inlines(request, obj)

    def get_list_filter(self, request):
        if es_operador(request.user):
            return ('category',)
        return super().get_list_filter(request)


@admin.register(SedeProduct)
class SedeProductAdmin(OperadorAdminMixin, admin.ModelAdmin):
    """Vista rápida para marcar disponible / no disponible por sede (HU11)."""
    campo_sede = 'sede'
    operador_puede_agregar = True
    operador_puede_editar = True
    list_display = ('product', 'sede', 'is_available')
    list_editable = ('is_available',)
    list_filter = ('sede', 'is_available')
    search_fields = ('product__name',)

    def get_list_filter(self, request):
        if es_operador(request.user):
            return ('is_available',)
        return super().get_list_filter(request)

    def get_readonly_fields(self, request, obj=None):
        if es_operador(request.user) and obj is not None:
            return ('sede', 'product')   # solo puede cambiar la disponibilidad
        return super().get_readonly_fields(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'sede' and es_operador(request.user):
            kwargs['queryset'] = Sede.objects.filter(pk=request.user.sede_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if es_operador(request.user) and request.user.sede_id:
            initial.setdefault('sede', request.user.sede_id)
        return initial


admin.site.site_header = 'DomiPedidosX · Administración'
admin.site.site_title = 'DomiPedidosX'
admin.site.index_title = 'Panel de administración'
