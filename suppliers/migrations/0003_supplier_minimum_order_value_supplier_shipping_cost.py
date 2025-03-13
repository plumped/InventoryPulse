# Generated by Django 5.1.7 on 2025-03-13 23:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0002_supplier_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplier',
            name='minimum_order_value',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Mindestbestellwert'),
        ),
        migrations.AddField(
            model_name='supplier',
            name='shipping_cost',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Versandkosten'),
        ),
    ]
