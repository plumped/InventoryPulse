# Generated by Django 5.1 on 2025-03-11 14:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_productvarianttype_product_has_batch_tracking_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='current_stock',
        ),
    ]
