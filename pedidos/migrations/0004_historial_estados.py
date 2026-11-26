from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0003_opciones_en_detalle'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistorialEstado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(choices=[('recibido', 'Recibido'), ('en_preparacion', 'En preparacion'), ('listo', 'Listo'), ('entregado', 'Entregado'), ('cancelado', 'Cancelado')], max_length=20, verbose_name='estado')),
                ('entrada', models.DateTimeField(default=django.utils.timezone.now, verbose_name='entrada al estado')),
                ('pedido', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historial_estados', to='pedidos.pedido')),
            ],
            options={
                'verbose_name': 'historial de estado',
                'verbose_name_plural': 'historial de estados',
                'ordering': ['entrada', 'id'],
            },
        ),
    ]
