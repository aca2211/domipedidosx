from django.urls import path

from . import views, views_operador


urlpatterns = [
    path('carrito/', views.ver_carrito, name='carrito_ver'),
    path('carrito/agregar/', views.agregar_al_carrito, name='carrito_agregar'),
    path('carrito/quitar/<int:producto_id>/', views.quitar_del_carrito, name='carrito_quitar'),
    path('carrito/actualizar/<int:producto_id>/', views.actualizar_carrito, name='carrito_actualizar'),
    path('mis-pedidos/', views.mis_pedidos, name='mis_pedidos'),
    path('pedido/confirmar/', views.confirmar_pedido, name='pedido_confirmar'),
    path('pedido/<int:pk>/cancelar/', views.cancelar_mi_pedido, name='pedido_cancelar'),
    path('pedido/<int:pk>/creado/', views.pedido_creado, name='pedido_creado'),
    path('operador/pedido/nuevo/', views_operador.elegir_cliente, name='operador_elegir_cliente'),
    path('operador/pedido/cliente/', views_operador.seleccionar_cliente, name='operador_seleccionar_cliente'),
]