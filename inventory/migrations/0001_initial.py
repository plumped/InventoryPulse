# Generated by Django 5.1.7 on 2025-04-04 07:52

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Warehouse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('location', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='StockTake',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Bezeichnung')),
                ('description', models.TextField(blank=True, verbose_name='Beschreibung')),
                ('status', models.CharField(choices=[('draft', 'Entwurf'), ('in_progress', 'In Bearbeitung'), ('completed', 'Abgeschlossen'), ('cancelled', 'Abgebrochen')], default='draft', max_length=20, verbose_name='Status')),
                ('start_date', models.DateTimeField(auto_now_add=True, verbose_name='Startdatum')),
                ('end_date', models.DateTimeField(blank=True, null=True, verbose_name='Enddatum')),
                ('notes', models.TextField(blank=True, verbose_name='Anmerkungen')),
                ('inventory_type', models.CharField(choices=[('full', 'Komplettinventur'), ('rolling', 'Rollierende Inventur'), ('blind', 'Blindzählung'), ('sample', 'Stichprobeninventur')], default='full', max_length=20, verbose_name='Inventurtyp')),
                ('display_expected_quantity', models.BooleanField(default=True, help_text='Wenn deaktiviert, werden den Zählern die erwarteten Mengen nicht angezeigt (Blindzählung)', verbose_name='Erwartete Mengen anzeigen')),
                ('cycle_count_category', models.CharField(blank=True, choices=[('A', 'A-Artikel (hoher Wert/Umschlag)'), ('B', 'B-Artikel (mittlerer Wert/Umschlag)'), ('C', 'C-Artikel (niedriger Wert/Umschlag)'), ('', 'Alle Artikel')], max_length=1, verbose_name='Artikelkategorie für rollierende Inventur')),
                ('count_frequency', models.IntegerField(default=0, help_text='0 = einmalige Inventur, >0 = Zyklus in Tagen für rollierende Inventur', verbose_name='Zählfrequenz in Tagen')),
                ('last_cycle_date', models.DateField(blank=True, null=True, verbose_name='Datum der letzten Zykleninventur')),
                ('completed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='stock_takes_completed', to=settings.AUTH_USER_MODEL, verbose_name='Abgeschlossen von')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_takes_created', to=settings.AUTH_USER_MODEL, verbose_name='Erstellt von')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.warehouse')),
            ],
            options={
                'verbose_name': 'Inventur',
                'verbose_name_plural': 'Inventuren',
                'ordering': ['-start_date'],
            },
        ),
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=2, max_digits=10)),
                ('movement_type', models.CharField(choices=[('in', 'Eingang'), ('out', 'Ausgang'), ('adj', 'Anpassung')], max_length=3)),
                ('reference', models.CharField(blank=True, max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.product')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.warehouse')),
            ],
        ),
        migrations.CreateModel(
            name='StockTakeItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expected_quantity', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Erwartete Menge')),
                ('counted_quantity', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Gezählte Menge')),
                ('is_counted', models.BooleanField(default=False, verbose_name='Gezählt')),
                ('notes', models.TextField(blank=True, verbose_name='Anmerkungen')),
                ('counted_at', models.DateTimeField(blank=True, null=True, verbose_name='Gezählt am')),
                ('counted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Gezählt von')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.product', verbose_name='Produkt')),
                ('stock_take', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.stocktake', verbose_name='Inventur')),
            ],
            options={
                'verbose_name': 'Inventurposition',
                'verbose_name_plural': 'Inventurpositionen',
                'ordering': ['product__name'],
                'unique_together': {('stock_take', 'product')},
            },
        ),
    ]
