from django.shortcuts import render
from .models import Sede, Category, Product

def menu_list(request):
    sedes = Sede.objects.filter(is_active=True)
    products = Product.objects.filter(is_available=True).select_related('category').prefetch_related('sede')
    sede_id = request.GET.get('sede')
    if sede_id:
        products = products.filter(sede__id=sede_id)
    categories = Category.objects.filter(products__in=products).distinct().order_by('name')
    return render(request, 'menu/menu_list.html', {
        'sedes': sedes,
        'products': products,
        'categories': categories,
        'sede_id': sede_id,
    })
