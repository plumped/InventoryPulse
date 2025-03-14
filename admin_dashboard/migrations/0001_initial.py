# Generated by Django 5.1.7 on 2025-03-12 18:30

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('inventory', '0003_stocktake_count_frequency_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminDashboardPermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
            options={
                'permissions': (('access_admin', 'Can access admin dashboard'),),
                'managed': False,
                'default_permissions': (),
            },
        ),
        migrations.CreateModel(
            name='WorkflowSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_approval_required', models.BooleanField(default=True, help_text='Müssen Bestellungen genehmigt werden?')),
                ('order_approval_threshold', models.DecimalField(decimal_places=2, default=1000.0, help_text='Bestellungen über diesem Wert erfordern eine Genehmigung', max_digits=10)),
                ('skip_draft_for_small_orders', models.BooleanField(default=False, help_text='Kleine Bestellungen direkt zur Genehmigung senden')),
                ('small_order_threshold', models.DecimalField(decimal_places=2, default=200.0, help_text='Schwellenwert für kleine Bestellungen', max_digits=10)),
                ('auto_approve_preferred_suppliers', models.BooleanField(default=False, help_text='Bestellungen von bevorzugten Lieferanten automatisch genehmigen')),
                ('send_order_emails', models.BooleanField(default=False, help_text='E-Mails für genehmigte Bestellungen senden')),
                ('require_separate_approver', models.BooleanField(default=True, help_text='Ersteller darf eigene Bestellung nicht genehmigen')),
            ],
            options={
                'verbose_name': 'Workflow-Einstellungen',
                'verbose_name_plural': 'Workflow-Einstellungen',
            },
        ),
        migrations.CreateModel(
            name='SystemSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(default='InventoryPulse', max_length=200)),
                ('company_logo', models.ImageField(blank=True, null=True, upload_to='company_logo/')),
                ('default_stock_min', models.IntegerField(default=10, help_text='Standardwert für Mindestbestand')),
                ('default_lead_time', models.IntegerField(default=7, help_text='Standardwert für Lieferzeit in Tagen')),
                ('email_notifications_enabled', models.BooleanField(default=False)),
                ('email_from_address', models.EmailField(blank=True, max_length=254, null=True)),
                ('next_order_number', models.IntegerField(default=1, help_text='Nächste Bestellnummer')),
                ('order_number_prefix', models.CharField(default='ORD-', help_text='Präfix für Bestellnummern', max_length=10)),
                ('track_inventory_history', models.BooleanField(default=True, help_text='Bestandsänderungen protokollieren')),
                ('auto_create_user_profile', models.BooleanField(default=True, help_text='Automatisch Benutzerprofile erstellen')),
                ('default_warehouse', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='default_warehouse_setting', to='inventory.warehouse')),
            ],
            options={
                'verbose_name': 'Systemeinstellungen',
                'verbose_name_plural': 'Systemeinstellungen',
            },
        ),
    ]
