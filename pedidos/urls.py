from django.urls import path

from . import views

urlpatterns = [
    path('carrito/', views.ver_carrito, name='carrito_ver'),
    path('carrito/agregar/', views.agregar_al_carrito, name='carrito_agregar'),
    path('carrito/quitar/<int:producto_id>/', views.quitar_del_carrito, name='carrito_quitar'),
    path('carrito/actualizar/<int:producto_id>/', views.actualizar_carrito, name='carrito_actualizar'),
]