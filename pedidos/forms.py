from django import forms

from .models import Pedido


class ConfirmarPedidoForm(forms.Form):
    direccion = forms.ModelChoiceField(queryset=None, label='Dirección de entrega', empty_label=None)
    metodo_pago = forms.ChoiceField(choices=Pedido.METODOS_PAGO, label='Método de pago (simulado)')
    observaciones = forms.CharField(
        label='Observaciones', required=False, max_length=300,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ej: sin cebolla, tocar el timbre...'}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['direccion'].queryset = user.direcciones.all()
        principal = user.direcciones.filter(is_default=True).first()
        if principal:
            self.fields['direccion'].initial = principal.pk
        for name, field in self.fields.items():
            clase = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs['class'] = clase


class PedidoOperadorForm(forms.Form):
    """Confirmación de un pedido que el operador toma en nombre de un cliente (HU15)."""
    tipo_entrega = forms.ChoiceField(
        choices=Pedido.TIPOS_ENTREGA, initial='domicilio', label='Tipo de entrega',
    )
    direccion = forms.ModelChoiceField(
        queryset=None, required=False, label='Dirección de entrega (del cliente)',
        empty_label='— Selecciona —',
    )
    metodo_pago = forms.ChoiceField(choices=Pedido.METODOS_PAGO, label='Método de pago (simulado)')
    observaciones = forms.CharField(
        label='Observaciones', required=False, max_length=300,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Ej: sin cebolla, tocar el timbre...'}),
    )

    def __init__(self, *args, cliente, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo las direcciones del cliente elegido: el operador no puede usar las de otro.
        self.fields['direccion'].queryset = cliente.direcciones.all()
        principal = cliente.direcciones.filter(is_default=True).first()
        if principal:
            self.fields['direccion'].initial = principal.pk
        for name, field in self.fields.items():
            clase = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs['class'] = clase

    def clean(self):
        datos = super().clean()
        if datos.get('tipo_entrega') == 'domicilio' and not datos.get('direccion'):
            self.add_error('direccion', 'Elige una dirección del cliente para el domicilio.')
        return datos
