# Generated by Django 5.1.7 on 2025-04-04 07:52

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        ('inventory', '0001_initial'),
        ('organization', '0001_initial'),
        ('suppliers', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='batchnumber',
            name='supplier',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='suppliers.supplier'),
        ),
        migrations.AddField(
            model_name='batchnumber',
            name='warehouse',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventory.warehouse'),
        ),
        migrations.AddField(
            model_name='importlog',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='import_logs', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='importerror',
            name='import_log',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='errors', to='core.importlog'),
        ),
        migrations.AddField(
            model_name='product',
            name='category',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.category'),
        ),
        migrations.AddField(
            model_name='batchnumber',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batches', to='core.product'),
        ),
        migrations.AddField(
            model_name='productattachment',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='core.product'),
        ),
        migrations.AddField(
            model_name='productphoto',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='core.product'),
        ),
        migrations.AddField(
            model_name='productvariant',
            name='parent_product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variants', to='core.product'),
        ),
        migrations.AddField(
            model_name='batchnumber',
            name='variant',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='batches', to='core.productvariant'),
        ),
        migrations.AddField(
            model_name='productvariant',
            name='variant_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.productvarianttype'),
        ),
        migrations.AddField(
            model_name='productwarehouse',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.product'),
        ),
        migrations.AddField(
            model_name='productwarehouse',
            name='warehouse',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.warehouse'),
        ),
        migrations.AddField(
            model_name='product',
            name='warehouses',
            field=models.ManyToManyField(through='core.ProductWarehouse', to='inventory.warehouse'),
        ),
        migrations.AddField(
            model_name='serialnumber',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='serial_numbers', to='core.product'),
        ),
        migrations.AddField(
            model_name='serialnumber',
            name='variant',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='serial_numbers', to='core.productvariant'),
        ),
        migrations.AddField(
            model_name='serialnumber',
            name='warehouse',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventory.warehouse'),
        ),
        migrations.AddField(
            model_name='product',
            name='tax',
            field=models.ForeignKey(blank=True, help_text='Der auf dieses Produkt anzuwendende Mehrwertsteuersatz', null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.tax', verbose_name='Mehrwertsteuersatz'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='departments',
            field=models.ManyToManyField(blank=True, related_name='user_profiles', to='organization.department'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='batchnumber',
            unique_together={('product', 'batch_number', 'warehouse')},
        ),
        migrations.AlterUniqueTogether(
            name='productvariant',
            unique_together={('parent_product', 'variant_type', 'value')},
        ),
        migrations.AlterUniqueTogether(
            name='productwarehouse',
            unique_together={('product', 'warehouse')},
        ),
    ]
