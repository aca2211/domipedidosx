import django.db.models.deletion
from django.db import migrations, models


def renombrar_estado(apps, schema_editor):
    Pedido = apps.get_model('pedidos', 'Pedido')
    Pedido.objects.filter(estado='preparando').update(estado='en_preparacion')


def revertir_estado(apps, schema_editor):
    Pedido = apps.get_model('pedidos', 'Pedido')
    Pedido.objects.filter(estado='en_preparacion').update(estado='preparando')


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='direccion',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='users.direccion'),
        ),
        migrations.AlterField(
            model_name='pedido',
            name='estado',
            field=models.CharField(choices=[('recibido', 'Recibido'), ('en_preparacion', 'En preparacion'), ('listo', 'Listo'), ('entregado', 'Entregado'), ('cancelado', 'Cancelado')], default='recibido', max_length=20),
        ),
        migrations.RunPython(renombrar_estado, revertir_estado),
    ]