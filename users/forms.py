from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import CustomUser


def _estilizar(form, placeholders=None):
    placeholders = placeholders or {}
    for name, field in form.fields.items():
        field.widget.attrs.setdefault('class', 'form-control')
        if name in placeholders:
            field.widget.attrs['placeholder'] = placeholders[name]


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

    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        labels = {'username': 'Usuario'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Contraseña'
        self.fields['password2'].label = 'Confirmar contraseña'
        _estilizar(self, {
            'username': 'Ej: andrea123',
            'email': 'tucorreo@ejemplo.com',
        })

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'cliente'   # el rol nunca viene del formulario público
        if commit:
            user.save()
        return user
