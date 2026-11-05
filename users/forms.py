import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import CustomUser, Direccion, phone_validator


def _estilizar(form, placeholders=None):
    placeholders = placeholders or {}
    for name, field in form.fields.items():
        field.widget.attrs.setdefault('class', 'form-control')
        if name in placeholders:
            field.widget.attrs['placeholder'] = placeholders[name]


def _limpiar_telefono(valor):
    telefono = re.sub(r'[\s\-().]', '', valor)
    phone_validator(telefono)
    return telefono


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Usuario', widget=forms.TextInput(attrs={'autofocus': True}))
    password = forms.CharField(label='Contraseña', strip=False, widget=forms.PasswordInput)

    error_messages = {
        'invalid_login': 'Usuario o contraseña incorrectos. Revisa los datos e inténtalo de nuevo.',
        'inactive': 'Esta cuenta está desactivada.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self, {'username': 'Tu nombre de usuario'})


class RegistroForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Correo electrónico')
    first_name = forms.CharField(max_length=150, required=True, label='Nombre')
    last_name = forms.CharField(max_length=150, required=True, label='Apellido')
    phone = forms.CharField(max_length=20, required=True, label='Teléfono de contacto')

    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'phone', 'password1', 'password2')
        labels = {'username': 'Usuario'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Contraseña'
        self.fields['password2'].label = 'Confirmar contraseña'
        _estilizar(self, {
            'username': 'Ej: andrea123',
            'email': 'tucorreo@ejemplo.com',
            'phone': 'Ej: 3001234567',
        })

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def clean_phone(self):
        phone = re.sub(r'[\s\-().]', '', self.cleaned_data['phone'])
        phone_validator(phone)
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'cliente'   # el rol nunca viene del formulario público
        if commit:
            user.save()
        return user


class PerfilForm(forms.ModelForm):
    """Datos de contacto editables del cliente (HU05). El rol y el usuario no se editan aquí."""
    first_name = forms.CharField(max_length=150, label='Nombre')
    last_name = forms.CharField(max_length=150, label='Apellido')
    email = forms.EmailField(label='Correo electrónico')
    phone = forms.CharField(max_length=20, label='Teléfono de contacto')

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self, {'email': 'tucorreo@ejemplo.com', 'phone': 'Ej: 3001234567'})

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Ya existe otra cuenta con este correo.')
        return email

    def clean_phone(self):
        return _limpiar_telefono(self.cleaned_data['phone'])


class DireccionForm(forms.ModelForm):
    class Meta:
        model = Direccion
        fields = ('label', 'address', 'details', 'is_default')
        labels = {
            'label': 'Nombre de la dirección',
            'address': 'Dirección',
            'details': 'Indicaciones para el domiciliario',
            'is_default': 'Usar como dirección principal',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self, {
            'label': 'Ej: Casa, Trabajo',
            'address': 'Ej: Calle 5 # 38-10, barrio Granada',
            'details': 'Ej: Apto 301, portería azul',
        })
        self.fields['is_default'].widget.attrs['class'] = 'form-check-input'
