from django.contrib import admin
from .models import Sede, Category, Product, ProductOption, SedeProduct


def es_operador(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'operador'


def producto_es_exclusivo(sede_id, producto):
    """True si el producto no se vende en ninguna otra sede (editarlo no afecta a nadie más)."""
    return bool(sede_id) and not SedeProduct.objects.filter(product=producto).exclude(sede_id=sede_id).exists()


def productos_exclusivos(sede_id):
    """Productos que se venden solo en esa sede: los únicos a los que su operador puede agregar opciones."""
    if not sede_id:
        return Product.objects.none()
    otras_sedes = SedeProduct.objects.exclude(sede_id=sede_id).values('product_id')
    return Product.objects.filter(sede_products__sede_id=sede_id).exclude(pk__in=otras_sedes)


class OperadorAdminMixin:
    """Reglas del rol operador en el admin (HU04, HU08, HU09, HU10, HU11).

    El operador siempre puede ver; agregar y editar dependen de los atributos de la clase
    (agregar además exige tener sede asignada); nunca puede borrar. Para editar un registro
    concreto, `operador_puede_editar_obj` decide (por defecto sí). Para cualquier otro usuario
    se aplican los permisos normales de Django.
    `campo_sede` es la ruta ORM hacia la sede para filtrar lo que ve (None = sin filtro).
    """
    campo_sede = None
    operador_puede_agregar = False
    operador_puede_editar = False

    def operador_puede_editar_obj(self, request, obj):
        return True

    def has_module_permission(self, request):
        return es_operador(request.user) or super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return es_operador(request.user) or super().has_view_permission(request, obj)

    def has_add_permission(self, request, *args):
        if es_operador(request.user):
            return self.operador_puede_agregar and bool(request.user.sede_id)
        return super().has_add_permission(request, *args)

    def has_change_permission(self, request, obj=None):
        if es_operador(request.user):
            if not self.operador_puede_editar:
                return False
            return obj is None or self.operador_puede_editar_obj(request, obj)
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
    """Categorías (HU08). Son globales: el operador las crea y ve todas (para poder elegirlas),
    pero solo edita las que no tienen productos de otras sedes."""
    operador_puede_agregar = True
    operador_puede_editar = True
    list_display = ('name', 'description')

    def operador_puede_editar_obj(self, request, obj):
        sede_id = request.user.sede_id
        if not sede_id:
            return False
        return not SedeProduct.objects.filter(product__category=obj).exclude(sede_id=sede_id).exists()


class SedeProductInline(admin.TabularInline):
    model = SedeProduct
    extra = 1


class ProductOptionInline(admin.TabularInline):
    """Tamaños, adiciones e ingredientes excluibles del producto (HU10)."""
    model = ProductOption
    extra = 1


@admin.register(Product)
class ProductAdmin(OperadorAdminMixin, admin.ModelAdmin):
    """Productos (HU09). El operador crea productos (quedan en su sede) y edita solo los que
    se venden únicamente en su sede; los compartidos con otras sedes los edita el administrador."""
    campo_sede = 'sedes'
    operador_puede_agregar = True
    operador_puede_editar = True
    list_display = ('name', 'category', 'price', 'prep_time_minutes')
    list_filter = ('category', 'sedes')
    search_fields = ('name',)
    inlines = [SedeProductInline, ProductOptionInline]

    def operador_puede_editar_obj(self, request, obj):
        return producto_es_exclusivo(request.user.sede_id, obj)

    def get_inlines(self, request, obj):
        if es_operador(request.user):
            return []   # los inlines mostrarían las demás sedes y las opciones compartidas
        return super().get_inlines(request, obj)

    def get_list_filter(self, request):
        if es_operador(request.user):
            return ('category',)
        return super().get_list_filter(request)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Sin el inline de sedes, el producto nuevo del operador se vincula solo a su sede.
        if es_operador(request.user) and not change and request.user.sede_id:
            SedeProduct.objects.get_or_create(sede_id=request.user.sede_id, product=form.instance)


@admin.register(ProductOption)
class ProductOptionAdmin(OperadorAdminMixin, admin.ModelAdmin):
    """Opciones de producto (HU10). Son del producto y se comparten entre sedes: el operador ve
    las de los productos de su sede, pero solo crea y edita las de productos exclusivos de su sede."""
    campo_sede = 'product__sedes'
    operador_puede_agregar = True
    operador_puede_editar = True
    list_display = ('name', 'kind', 'product', 'extra_price', 'is_active')
    list_filter = ('kind', 'is_active')
    search_fields = ('name', 'product__name')

    def operador_puede_editar_obj(self, request, obj):
        return producto_es_exclusivo(request.user.sede_id, obj.product)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'product' and es_operador(request.user):
            kwargs['queryset'] = productos_exclusivos(request.user.sede_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_list_filter(self, request):
        if es_operador(request.user):
            return ('kind', 'is_active')
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
