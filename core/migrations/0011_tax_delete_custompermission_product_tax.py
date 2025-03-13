# Generated by Django 5.1.7 on 2025-03-13 20:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_alter_userprofile_departments'),
    ]

    operations = [
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
        migrations.DeleteModel(
            name='CustomPermission',
        ),
        migrations.AddField(
            model_name='product',
            name='tax',
            field=models.ForeignKey(blank=True, help_text='Der auf dieses Produkt anzuwendende Mehrwertsteuersatz', null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.tax', verbose_name='Mehrwertsteuersatz'),
        ),
    ]
