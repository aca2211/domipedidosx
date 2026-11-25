from django.urls import path

from . import views, views_cocina, views_operador, views_repetir


from .views_historial_sede import historial_sede
from .views_busqueda import buscar_clientes, buscar_pedidos

urlpatterns = [
    path('carrito/', views.ver_carrito, name='carrito_ver'),
    path('carrito/agregar/', views.agregar_al_carrito, name='carrito_agregar'),
    path('carrito/quitar/<str:clave>/', views.quitar_del_carrito, name='carrito_quitar'),
    path('carrito/actualizar/<str:clave>/', views.actualizar_carrito, name='carrito_actualizar'),
    path('mis-pedidos/', views.mis_pedidos, name='mis_pedidos'),
    path('pedido/confirmar/', views.confirmar_pedido, name='pedido_confirmar'),
    path('pedido/<int:pk>/cancelar/', views.cancelar_mi_pedido, name='pedido_cancelar'),
    path('pedido/<int:pk>/repetir/', views_repetir.repetir_mi_pedido, name='pedido_repetir'),
    path('pedido/<int:pk>/creado/', views.pedido_creado, name='pedido_creado'),
    path('cocina/tablero/', views_cocina.tablero_cocina, name='cocina_tablero'),
    path('cocina/pedido/<int:pk>/avanzar/', views_cocina.avanzar_estado, name='cocina_avanzar'),
    path('operador/panel/', views_operador.panel_operador, name='operador_panel'),
    path('operador/pedido/<int:pk>/asignar/', views_operador.asignar_repartidor_pedido, name='operador_asignar_repartidor'),
    path('operador/historial/', historial_sede, name='operador_historial'),
    path('gestion/pedidos/', buscar_pedidos, name='buscar_pedidos'),
    path('gestion/clientes/', buscar_clientes, name='buscar_clientes'),
    path('operador/pedido/nuevo/', views_operador.elegir_cliente, name='operador_elegir_cliente'),
    path('operador/pedido/cliente/', views_operador.seleccionar_cliente, name='operador_seleccionar_cliente'),
    path('operador/pedido/armar/', views_operador.armar_pedido, name='operador_armar_pedido'),
    path('operador/pedido/agregar/', views_operador.agregar_producto, name='operador_agregar'),
    path('operador/pedido/actualizar/<str:clave>/', views_operador.actualizar_linea, name='operador_actualizar'),
    path('operador/pedido/quitar/<str:clave>/', views_operador.quitar_linea, name='operador_quitar'),
    path('operador/pedido/confirmar/', views_operador.confirmar_pedido_operador, name='operador_confirmar'),
    path('operador/pedido/<int:pk>/creado/', views_operador.pedido_creado_operador, name='operador_pedido_creado'),
]
