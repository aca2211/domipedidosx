from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Pedido

@login_required
def pedidos_list(request):
    pedidos = Pedido.objects.filter(cliente=request.user).order_by("-id") 
    return render(request, 'pedidos/pedidos_list.html', {'pedidos': pedidos})