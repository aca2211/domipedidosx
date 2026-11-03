from django.db.models import Prefetch
from django.shortcuts import render
from .models import Sede, Category, Product, SedeProduct

def menu_list(request):
    sedes = Sede.objects.filter(is_active=True)
    sede_id = request.GET.get('sede', '')
    if not sede_id.isdigit():
        sede_id = ''

    # Un producto se muestra si está disponible en al menos una sede activa
    # (o en la sede elegida con el filtro).
    disponibles = SedeProduct.objects.filter(is_available=True, sede__is_active=True)
    if sede_id:
        disponibles = disponibles.filter(sede_id=sede_id)

    products = (
        Product.objects.filter(pk__in=disponibles.values('product'))
        .select_related('category')
        .prefetch_related(Prefetch(
            'sede_products',
            queryset=SedeProduct.objects.filter(is_available=True, sede__is_active=True).select_related('sede'),
            to_attr='sedes_disponibles',
        ))
    )
    categories = Category.objects.filter(products__in=products).distinct().order_by('name')
    return render(request, 'menu/menu_list.html', {
        'sedes': sedes,
        'products': products,
        'categories': categories,
        'sede_id': sede_id,
    })
