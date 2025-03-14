from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from suppliers.models import Supplier


class InterfaceType(models.Model):
    """Definiert die verfügbaren Schnittstellentypen"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Schnittstellentyp")
        verbose_name_plural = _("Schnittstellentypen")
        ordering = ['name']


class SupplierInterface(models.Model):
    """Konfiguration für Lieferantenschnittstellen"""
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.CASCADE, 
        related_name='interfaces',
        verbose_name=_("Lieferant")
    )
    interface_type = models.ForeignKey(
        InterfaceType, 
        on_delete=models.PROTECT,
        verbose_name=_("Schnittstellentyp")
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("Bezeichnung")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Aktiv")
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Standard")
    )
    
    # Gemeinsame Felder für alle Schnittstellentypen
    api_url = models.URLField(
        blank=True, 
        null=True,
        verbose_name=_("API-URL")
    )
    username = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name=_("Benutzername")
    )
    password = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name=_("Passwort")
    )
    api_key = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name=_("API-Schlüssel")
    )
    
    # SFTP/FTP Konfiguration
    host = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name=_("Host")
    )
    port = models.IntegerField(
        blank=True, 
        null=True,
        verbose_name=_("Port")
    )
    remote_path = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name=_("Remote-Pfad")
    )
    
    # E-Mail Konfiguration
    email_to = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name=_("E-Mail-Empfänger")
    )
    email_cc = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name=_("E-Mail-CC")
    )
    email_subject_template = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name=_("E-Mail-Betreffvorlage")
    )
    
    # Format-Konfiguration
    order_format = models.CharField(
        max_length=50, 
        choices=[
            ('csv', 'CSV'),
            ('xml', 'XML'),
            ('json', 'JSON'),
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('custom', 'Benutzerdefiniert')
        ],
        default='csv',
        verbose_name=_("Bestellformat")
    )
    
    # Zusätzliche Konfiguration als JSON
    config_json = models.JSONField(
        blank=True, 
        null=True,
        verbose_name=_("Zusätzliche Konfiguration")
    )
    
    # Formatierungsvorlagen (z.B. für XML oder CSV)
    template = models.TextField(
        blank=True,
        verbose_name=_("Formatierungsvorlage")
    )
    
    # Logging und Tracking
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_interfaces',
        verbose_name=_("Erstellt von")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Erstellt am")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Aktualisiert am")
    )
    last_used = models.DateTimeField(
        blank=True, 
        null=True,
        verbose_name=_("Zuletzt verwendet")
    )
    
    def __str__(self):
        return f"{self.supplier.name} - {self.name} ({self.interface_type.name})"
    
    def save(self, *args, **kwargs):
        # Wenn diese Schnittstelle als Standard markiert ist, andere für den gleichen Lieferanten zurücksetzen
        if self.is_default:
            SupplierInterface.objects.filter(
                supplier=self.supplier, 
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
            
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = _("Lieferantenschnittstelle")
        verbose_name_plural = _("Lieferantenschnittstellen")
        unique_together = ('supplier', 'name')
        ordering = ['supplier__name', 'name']


class InterfaceLog(models.Model):
    """Protokolliert Übertragungen über Schnittstellen"""
    
    STATUS_CHOICES = [
        ('pending', _('Ausstehend')),
        ('in_progress', _('In Bearbeitung')),
        ('success', _('Erfolgreich')),
        ('failed', _('Fehlgeschlagen')),
        ('retry', _('Wiederholung'))
    ]
    
    interface = models.ForeignKey(
        SupplierInterface, 
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name=_("Schnittstelle")
    )
    order = models.ForeignKey(
        'order.PurchaseOrder', 
        on_delete=models.CASCADE,
        related_name='interface_logs',
        verbose_name=_("Bestellung")
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Zeitstempel")
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Status")
    )
    message = models.TextField(
        blank=True,
        verbose_name=_("Nachricht")
    )
    request_data = models.TextField(
        blank=True,
        verbose_name=_("Gesendete Daten")
    )
    response_data = models.TextField(
        blank=True,
        verbose_name=_("Empfangene Daten")
    )
    initiated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name=_("Ausgelöst von")
    )
    attempt_count = models.IntegerField(
        default=1,
        verbose_name=_("Versuchszähler")
    )
    
    def __str__(self):
        return f"{self.order.order_number} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {self.get_status_display()}"
    
    class Meta:
        verbose_name = _("Schnittstellen-Log")
        verbose_name_plural = _("Schnittstellen-Logs")
        ordering = ['-timestamp']