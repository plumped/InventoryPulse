# admin_dashboard/models.py
from django.db import models
from django.conf import settings


# Custom Permission Model
class AdminDashboardPermission(models.Model):
    """Model for admin dashboard permissions."""

    class Meta:
        managed = False  # No database table creation
        default_permissions = ()
        permissions = (
            ('access_admin', 'Can access admin dashboard'),
        )


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