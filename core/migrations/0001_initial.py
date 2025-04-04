# Generated by Django 5.1.7 on 2025-04-04 07:52

import core.models
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BatchNumber',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_number', models.CharField(max_length=100)),
                ('quantity', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('production_date', models.DateField(blank=True, null=True)),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'Kategorie',
                'verbose_name_plural': 'Kategorien',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(help_text='ISO 4217 currency code (e.g., EUR, USD)', max_length=3, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('symbol', models.CharField(max_length=5)),
                ('decimal_places', models.IntegerField(default=2)),
                ('is_default', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('exchange_rate', models.DecimalField(decimal_places=6, default=1.0, help_text='Exchange rate relative to the default currency', max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Währung',
                'verbose_name_plural': 'Währungen',
                'ordering': ['code'],
            },
        ),
        migrations.CreateModel(
            name='ImportError',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('row_number', models.IntegerField()),
                ('error_message', models.TextField()),
                ('row_data', models.TextField(blank=True)),
                ('field_name', models.CharField(blank=True, max_length=100)),
                ('field_value', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['row_number'],
            },
        ),
        migrations.CreateModel(
            name='ImportLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255)),
                ('import_type', models.CharField(choices=[('products', 'Products'), ('categories', 'Categories'), ('suppliers', 'Suppliers'), ('supplier_products', 'Supplier Products'), ('warehouses', 'Warehouses'), ('departments', 'Departments'), ('warehouse_products', 'Warehouse Products')], default='products', max_length=50)),
                ('status', models.CharField(choices=[('completed', 'Completed'), ('completed_with_errors', 'Completed with Errors'), ('processing', 'Processing'), ('failed', 'Failed')], default='processing', max_length=25)),
                ('total_records', models.IntegerField(default=0)),
                ('success_count', models.IntegerField(default=0)),
                ('error_count', models.IntegerField(default=0)),
                ('rows_processed', models.IntegerField(default=0)),
                ('rows_created', models.IntegerField(default=0)),
                ('rows_updated', models.IntegerField(default=0)),
                ('rows_error', models.IntegerField(default=0)),
                ('error_file', models.FileField(blank=True, null=True, upload_to='import_errors/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('error_details', models.TextField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('sku', models.CharField(max_length=50, unique=True)),
                ('barcode', models.CharField(blank=True, max_length=100)),
                ('description', models.TextField(blank=True)),
                ('minimum_stock', models.IntegerField(default=0)),
                ('unit', models.CharField(default='Stück', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('has_variants', models.BooleanField(default=False)),
                ('has_serial_numbers', models.BooleanField(default=False)),
                ('has_batch_tracking', models.BooleanField(default=False)),
                ('has_expiry_tracking', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='ProductAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to=core.models.attachment_path)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('file_type', models.CharField(blank=True, max_length=100)),
                ('upload_date', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-upload_date'],
            },
        ),
        migrations.CreateModel(
            name='ProductPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='product_photos/')),
                ('is_primary', models.BooleanField(default=False)),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('upload_date', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-is_primary', '-upload_date'],
            },
        ),
        migrations.CreateModel(
            name='ProductVariant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sku', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('value', models.CharField(max_length=100)),
                ('price_adjustment', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('barcode', models.CharField(blank=True, max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['parent_product', 'variant_type', 'value'],
            },
        ),
        migrations.CreateModel(
            name='ProductVariantType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ProductWarehouse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
            ],
        ),
        migrations.CreateModel(
            name='SerialNumber',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('serial_number', models.CharField(max_length=100, unique=True)),
                ('status', models.CharField(choices=[('in_stock', 'Auf Lager'), ('sold', 'Verkauft'), ('reserved', 'Reserviert'), ('defective', 'Defekt'), ('returned', 'Zurückgegeben')], default='in_stock', max_length=20)),
                ('purchase_date', models.DateField(blank=True, null=True)),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Tax',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('code', models.CharField(max_length=20, unique=True, verbose_name='Steuerkürzel')),
                ('rate', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='Steuersatz (%)')),
                ('description', models.TextField(blank=True, verbose_name='Beschreibung')),
                ('is_default', models.BooleanField(default=False, verbose_name='Standard-Steuersatz')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')),
            ],
            options={
                'verbose_name': 'Mehrwertsteuersatz',
                'verbose_name_plural': 'Mehrwertsteuersätze',
                'ordering': ['rate'],
            },
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
    ]
