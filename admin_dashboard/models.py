# admin_dashboard/models.py
from django.db import models
from django.db import transaction
from django.conf import settings


# Workflow-Einstellungen
class WorkflowSettings(models.Model):
    """Settings for workflow processes."""
    # Bestellprozess
    order_approval_required = models.BooleanField(
        default=True,
        help_text="Müssen Bestellungen genehmigt werden?"
    )
    order_approval_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1000.00,
        help_text="Bestellungen über diesem Wert erfordern eine Genehmigung"
    )

    # Workflow-Stufen und Vereinfachungsoptionen
    skip_draft_for_small_orders = models.BooleanField(
        default=False,
        help_text="Kleine Bestellungen direkt zur Genehmigung senden"
    )
    small_order_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=200.00,
        help_text="Schwellenwert für kleine Bestellungen"
    )
    auto_approve_preferred_suppliers = models.BooleanField(
        default=False,
        help_text="Bestellungen von bevorzugten Lieferanten automatisch genehmigen"
    )
    send_order_emails = models.BooleanField(
        default=False,
        help_text="E-Mails für genehmigte Bestellungen senden"
    )

    # Benutzerrollen im Workflow
    require_separate_approver = models.BooleanField(
        default=True,
        help_text="Ersteller darf eigene Bestellung nicht genehmigen"
    )

    class Meta:
        verbose_name = "Workflow-Einstellungen"
        verbose_name_plural = "Workflow-Einstellungen"


# System-Einstellungen
class SystemSettings(models.Model):
    """Model for system-wide settings."""
    company_name = models.CharField(max_length=200, default="InventoryPulse")
    company_logo = models.ImageField(upload_to='company_logo/', blank=True, null=True)
    default_warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name='default_warehouse_setting')
    default_stock_min = models.IntegerField(default=10, help_text="Standardwert für Mindestbestand")
    default_lead_time = models.IntegerField(default=7, help_text="Standardwert für Lieferzeit in Tagen")

    # E-Mail-Einstellungen
    email_notifications_enabled = models.BooleanField(default=False)
    email_from_address = models.EmailField(blank=True, null=True)

    # Optionen für Nummerierung
    next_order_number = models.IntegerField(default=1, help_text="Nächste Bestellnummer")
    order_number_prefix = models.CharField(max_length=10, default="ORD-", help_text="Präfix für Bestellnummern")

    # Systemweite Logik
    track_inventory_history = models.BooleanField(default=True, help_text="Bestandsänderungen protokollieren")

    # Migration-Spezifische Settings
    auto_create_user_profile = models.BooleanField(default=True, help_text="Automatisch Benutzerprofile erstellen")

    class Meta:
        verbose_name = "Systemeinstellungen"
        verbose_name_plural = "Systemeinstellungen"


class CompanyAddressType(models.TextChoices):
    HEADQUARTERS = 'headquarters', 'Hauptsitz'
    WAREHOUSE = 'warehouse', 'Lager'
    SHIPPING = 'shipping', 'Versandadresse'
    RETURN = 'return', 'Rücksendeadresse'
    BILLING = 'billing', 'Rechnungsadresse'
    OTHER = 'other', 'Sonstige'


class CompanyAddress(models.Model):
    """Model für Unternehmensadressen"""
    name = models.CharField(max_length=100, verbose_name="Bezeichnung")
    address_type = models.CharField(
        max_length=20,
        choices=CompanyAddressType.choices,
        verbose_name="Adresstyp"
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="Standardadresse für diesen Typ"
    )
    street = models.CharField(max_length=255, verbose_name="Straße und Hausnummer")
    zip_code = models.CharField(max_length=20, verbose_name="PLZ")
    city = models.CharField(max_length=100, verbose_name="Ort")
    country = models.CharField(max_length=100, verbose_name="Land")
    contact_person = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Ansprechpartner"
    )
    phone = models.CharField(max_length=50, blank=True, verbose_name="Telefon")
    email = models.EmailField(blank=True, verbose_name="E-Mail")
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        verbose_name = "Unternehmensadresse"
        verbose_name_plural = "Unternehmensadressen"
        ordering = ['address_type', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['address_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_company_address_per_type'  # Geändert, um eindeutig zu sein
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_address_type_display()})"

    @property
    def full_address(self):
        """Gibt eine formatierte vollständige Adresse zurück"""
        address = f"{self.street}\n{self.zip_code} {self.city}"
        if self.country:
            address += f"\n{self.country}"
        return address

    def save(self, *args, **kwargs):
        """Überschreibe save, um sicherzustellen, dass nur eine Standardadresse
        pro Adresstyp existiert."""
        if self.is_default:
            # Wenn diese Adresse als Standard markiert ist, setze alle anderen
            # Adressen desselben Typs auf nicht-Standard
            with transaction.atomic():
                CompanyAddress.objects.filter(
                    address_type=self.address_type,
                    is_default=True
                ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)