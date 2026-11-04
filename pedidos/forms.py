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