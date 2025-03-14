# Generated by Django 5.1.7 on 2025-03-12 13:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_remove_productvariant_current_stock'),
        ('inventory', '0003_stocktake_count_frequency_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='batchnumber',
            unique_together={('product', 'batch_number', 'warehouse')},
        ),
    ]
