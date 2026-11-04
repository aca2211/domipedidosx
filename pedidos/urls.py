from django.urls import path
from . import views

urlpatterns = [
    path('cocina/', views.pedidos_list, name='pedidos_list'),
]
    