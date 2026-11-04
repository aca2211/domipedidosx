from django.urls import path
from . import views

urlpatterns = [
    path('pedidos/', views.pedidos_list, name='pedidos_list'),
]
    