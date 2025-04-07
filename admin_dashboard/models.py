from django.db import models, transaction


class WorkflowSettings(models.Model):
    """Einstellungen für Genehmigungs-Workflows."""
    order_approval_required = models.BooleanField(default=True, help_text="Müssen Bestellungen genehmigt werden?")
    order_approval_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00, help_text="Genehmigung ab diesem Wert erforderlich")
    skip_draft_for_small_orders = models.BooleanField(default=False, help_text="Kleine Bestellungen direkt zur Genehmigung senden")
    small_order_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=200.00, help_text="Schwellenwert für kleine Bestellungen")
    auto_approve_preferred_suppliers = models.BooleanField(default=False, help_text="Bevorzugte Lieferanten automatisch genehmigen")
    send_order_emails = models.BooleanField(default=False, help_text="E-Mails bei genehmigten Bestellungen senden")
    require_separate_approver = models.BooleanField(default=True, help_text="Ersteller darf eigene Bestellung nicht genehmigen")

    class Meta:
        verbose_name = "Workflow-Einstellungen"
        verbose_name_plural = "Workflow-Einstellungen"


class SystemSettings(models.Model):
    """Systemweite Konfiguration."""
    company_name = models.CharField(max_length=200, default="InventoryPulse")
    company_logo = models.ImageField(upload_to='company_logo/', null=True, blank=True)
    default_warehouse = models.ForeignKey('inventory.Warehouse', null=True, blank=True, on_delete=models.SET_NULL, related_name='default_warehouse_setting')
    default_stock_min = models.IntegerField(default=10, help_text="Standard-Mindestbestand")
    default_lead_time = models.IntegerField(default=7, help_text="Standard-Lieferzeit in Tagen")
    email_notifications_enabled = models.BooleanField(default=False)
    email_from_address = models.EmailField(null=True, blank=True)
    next_order_number = models.IntegerField(default=1, help_text="Nächste Bestellnummer")
    order_number_prefix = models.CharField(max_length=10, default="ORD-", help_text="Präfix für Bestellnummern")
    track_inventory_history = models.BooleanField(default=True, help_text="Bestandsänderungen protokollieren")
    auto_create_user_profile = models.BooleanField(default=True, help_text="Benutzerprofile automatisch anlegen")

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
    name = models.CharField(max_length=100)
    address_type = models.CharField(max_length=20, choices=CompanyAddressType.choices)
    is_default = models.BooleanField(default=False, help_text="Standardadresse für diesen Typ")
    street = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Unternehmensadresse"
        verbose_name_plural = "Unternehmensadressen"
        ordering = ['address_type', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['address_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_company_address_per_type'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_address_type_display()})"

    @property
    def full_address(self):
        parts = [self.street, f"{self.zip_code} {self.city}", self.country]
        return "\n".join(p for p in parts if p)

    def save(self, *args, **kwargs):
        if self.is_default:
            with transaction.atomic():
                CompanyAddress.objects.filter(
                    address_type=self.address_type,
                    is_default=True
                ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
