from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0003_feriados_parametros'),
    ]

    operations = [
        migrations.AddField(
            model_name='sedeproduct',
            name='stock',
            field=models.PositiveIntegerField(blank=True, help_text='Unidades en inventario. Vacío = sin control de existencias.', null=True, verbose_name='existencias'),
        ),
        migrations.AddField(
            model_name='sedeproduct',
            name='stock_minimo',
            field=models.PositiveIntegerField(default=0, help_text='Cuando las existencias llegan a este número, el operador recibe una alerta para reponer.', verbose_name='stock mínimo'),
        ),
    ]
