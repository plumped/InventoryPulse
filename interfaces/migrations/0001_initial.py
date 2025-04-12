# Generated by Django 5.1.7 on 2025-04-11 22:30

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InterfaceType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('code', models.CharField(max_length=50, unique=True)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Schnittstellentyp',
                'verbose_name_plural': 'Schnittstellentypen',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='SupplierInterface',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Bezeichnung')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('is_default', models.BooleanField(default=False, verbose_name='Standard')),
                ('api_url', models.URLField(blank=True, null=True, verbose_name='API-URL')),
                ('username', models.CharField(blank=True, max_length=100, verbose_name='Benutzername')),
                ('password', models.CharField(blank=True, max_length=100, verbose_name='Passwort')),
                ('api_key', models.CharField(blank=True, max_length=255, verbose_name='API-Schlüssel')),
                ('host', models.CharField(blank=True, max_length=255, verbose_name='Host')),
                ('port', models.IntegerField(blank=True, null=True, verbose_name='Port')),
                ('remote_path', models.CharField(blank=True, max_length=255, verbose_name='Remote-Pfad')),
                ('email_to', models.CharField(blank=True, max_length=255, verbose_name='E-Mail-Empfänger')),
                ('email_cc', models.CharField(blank=True, max_length=255, verbose_name='E-Mail-CC')),
                ('email_subject_template',
                 models.CharField(blank=True, max_length=255, verbose_name='E-Mail-Betreffvorlage')),
                ('order_format', models.CharField(
                    choices=[('csv', 'CSV'), ('xml', 'XML'), ('json', 'JSON'), ('pdf', 'PDF'), ('excel', 'Excel'),
                             ('custom', 'Benutzerdefiniert')], default='csv', max_length=50,
                    verbose_name='Bestellformat')),
                ('config_json', models.JSONField(blank=True, null=True, verbose_name='Zusätzliche Konfiguration')),
                ('template', models.TextField(blank=True, verbose_name='Formatierungsvorlage')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')),
                ('last_used', models.DateTimeField(blank=True, null=True, verbose_name='Zuletzt verwendet')),
            ],
            options={
                'verbose_name': 'Lieferantenschnittstelle',
                'verbose_name_plural': 'Lieferantenschnittstellen',
                'ordering': ['supplier__name', 'name'],
            },
        ),
        migrations.CreateModel(
            name='XMLStandardTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Name')),
                ('code', models.CharField(max_length=50, unique=True, verbose_name='Code')),
                ('description', models.TextField(blank=True, verbose_name='Beschreibung')),
                ('template', models.TextField(verbose_name='XML-Vorlage')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('industry', models.CharField(blank=True, max_length=100, verbose_name='Branche')),
                ('version', models.CharField(blank=True, max_length=50, verbose_name='Version')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')),
            ],
            options={
                'verbose_name': 'XML-Standardvorlage',
                'verbose_name_plural': 'XML-Standardvorlagen',
                'ordering': ['name', 'version'],
            },
        ),
        migrations.CreateModel(
            name='InterfaceLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Zeitstempel')),
                ('status', models.CharField(
                    choices=[('pending', 'Ausstehend'), ('in_progress', 'In Bearbeitung'), ('success', 'Erfolgreich'),
                             ('failed', 'Fehlgeschlagen'), ('retry', 'Wiederholung')], default='pending', max_length=20,
                    verbose_name='Status')),
                ('message', models.TextField(blank=True, verbose_name='Nachricht')),
                ('request_data', models.TextField(blank=True, verbose_name='Gesendete Daten')),
                ('response_data', models.TextField(blank=True, verbose_name='Empfangene Daten')),
                ('attempt_count', models.IntegerField(default=1, verbose_name='Versuchszähler')),
                ('initiated_by',
                 models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL,
                                   verbose_name='Ausgelöst von')),
            ],
            options={
                'verbose_name': 'Schnittstellen-Log',
                'verbose_name_plural': 'Schnittstellen-Logs',
                'ordering': ['-timestamp'],
            },
        ),
    ]
