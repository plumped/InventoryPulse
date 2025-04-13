from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from inventory.models import Warehouse
from order.models import PurchaseOrder, PurchaseOrderReceiptItem
from product_management.models.products import Product
from suppliers.models import SupplierProduct


class RMAStatus(models.TextChoices):
    DRAFT = 'draft', 'Entwurf'
    PENDING = 'pending', 'In Bearbeitung'
    APPROVED = 'approved', 'Genehmigt'
    SENT = 'sent', 'An Lieferant gesendet'
    RESOLVED = 'resolved', 'Erledigt'
    REJECTED = 'rejected', 'Abgelehnt'
    CANCELLED = 'cancelled', 'Storniert'


class RMAResolutionType(models.TextChoices):
    REPLACEMENT = 'replacement', 'Ersatz'
    REFUND = 'refund', 'Rückerstattung'
    CREDIT = 'credit', 'Gutschrift'
    REPAIR = 'repair', 'Reparatur'
    NO_ACTION = 'no_action', 'Keine Maßnahme'


class RMA(models.Model):
    """Model für Return Merchandise Authorization (RMA)."""

    # RMA Number Generation Metadata
    rma_number = models.CharField(max_length=50, unique=True, verbose_name="RMA-Nummer")

    # Basic info
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.PROTECT, verbose_name="Lieferant")
    related_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='rmas', verbose_name="Zugehörige Bestellung")

    # Status management
    status = models.CharField(max_length=20, choices=RMAStatus.choices, default=RMAStatus.DRAFT, verbose_name="Status")

    # Resolution type and details
    resolution_type = models.CharField(max_length=20, choices=RMAResolutionType.choices, null=True, blank=True,
                                       verbose_name="Art der Lösung")
    resolution_notes = models.TextField(blank=True, verbose_name="Lösungsdetails")

    # RMA Warehouse - where defective items will be stored
    rma_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT,
                                      related_name='rma_items', verbose_name="RMA-Lager")

    # Important dates
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    submission_date = models.DateTimeField(null=True, blank=True, verbose_name="Eingereicht am")
    resolution_date = models.DateTimeField(null=True, blank=True, verbose_name="Gelöst am")

    # User tracking
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_rmas',
                                   verbose_name="Erstellt von")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='approved_rmas', verbose_name="Genehmigt von")

    # Contact and shipping information
    contact_person = models.CharField(max_length=100, blank=True, verbose_name="Kontaktperson")
    contact_email = models.EmailField(blank=True, verbose_name="Kontakt E-Mail")
    contact_phone = models.CharField(max_length=50, blank=True, verbose_name="Kontakt Telefon")

    shipping_address = models.TextField(blank=True, verbose_name="Rücksendeadresse")
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name="Tracking-Nummer")
    shipping_date = models.DateField(null=True, blank=True, verbose_name="Versanddatum")

    # Financial information
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),
                                      verbose_name="Gesamtwert")

    # Notes
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")

    def __str__(self):
        return self.rma_number

    def update_total_value(self):
        """Updates the total value of this RMA based on all items."""
        total = sum(item.value for item in self.items.all())
        self.total_value = total
        self.save(update_fields=['total_value'])

    def update_status(self, new_status, user=None):
        """Updates the status with tracking of date changes."""
        old_status = self.status
        self.status = new_status

        # Update status-specific timestamps
        if new_status == RMAStatus.APPROVED and old_status != RMAStatus.APPROVED:
            # Record approval details
            self.approved_by = user

        elif new_status == RMAStatus.PENDING and old_status == RMAStatus.DRAFT:
            # Record submission date when first moved to pending
            self.submission_date = timezone.now()

        elif new_status == RMAStatus.RESOLVED and old_status != RMAStatus.RESOLVED:
            # Record resolution date
            self.resolution_date = timezone.now()

        self.save()

        # Create status change entry in history
        RMAHistory.objects.create(
            rma=self,
            status_from=old_status,
            status_to=new_status,
            changed_by=user,
            note=f"Status geändert: {RMAStatus(old_status).label} → {RMAStatus(new_status).label}"
        )

    def submit(self, user):
        """Submit the RMA for processing."""
        if self.status != RMAStatus.DRAFT:
            raise ValueError("Nur Entwürfe können eingereicht werden.")
        self.update_status(RMAStatus.PENDING, user)

    def approve(self, user):
        """Approve the RMA."""
        if self.status != RMAStatus.PENDING:
            raise ValueError("Nur RMAs im Status 'In Bearbeitung' können genehmigt werden.")
        self.update_status(RMAStatus.APPROVED, user)

    def mark_sent(self, user, tracking_number=None, shipping_date=None):
        """Mark the RMA as sent to supplier."""
        if self.status != RMAStatus.APPROVED:
            raise ValueError("Nur genehmigte RMAs können als gesendet markiert werden.")

        if tracking_number:
            self.tracking_number = tracking_number

        if shipping_date:
            self.shipping_date = shipping_date
        elif not self.shipping_date:
            self.shipping_date = timezone.now().date()

        self.update_status(RMAStatus.SENT, user)

    def resolve(self, user, resolution_type, resolution_notes=""):
        """Mark the RMA as resolved with specified resolution."""
        if self.status not in [RMAStatus.SENT, RMAStatus.APPROVED]:
            raise ValueError("Nur gesendete oder genehmigte RMAs können als erledigt markiert werden.")

        self.resolution_type = resolution_type
        self.resolution_notes = resolution_notes
        self.update_status(RMAStatus.RESOLVED, user)

    def cancel(self, user, reason=""):
        """Cancel the RMA."""
        if self.status in [RMAStatus.RESOLVED, RMAStatus.CANCELLED]:
            raise ValueError("Erledigte oder bereits stornierte RMAs können nicht storniert werden.")

        self.update_status(RMAStatus.CANCELLED, user)

        # Create a note about the cancellation reason
        if reason:
            RMAHistory.objects.create(
                rma=self,
                status_from=self.status,
                status_to=self.status,
                changed_by=user,
                note=f"Stornierungsgrund: {reason}"
            )

    def reject(self, user, reason=""):
        """Reject the RMA, usually during the approval process."""
        if self.status != RMAStatus.PENDING:
            raise ValueError("Nur RMAs im Status 'In Bearbeitung' können abgelehnt werden.")

        self.update_status(RMAStatus.REJECTED, user)

        # Create a note about the rejection reason
        if reason:
            RMAHistory.objects.create(
                rma=self,
                status_from=RMAStatus.PENDING,
                status_to=RMAStatus.REJECTED,
                changed_by=user,
                note=f"Ablehnungsgrund: {reason}"
            )

    class Meta:
        verbose_name = "RMA"
        verbose_name_plural = "RMAs"
        ordering = ['-created_at']


class RMAIssueType(models.TextChoices):
    DEFECTIVE = 'defective', 'Defekt'
    DAMAGED = 'damaged', 'Beschädigt'
    WRONG_ITEM = 'wrong_item', 'Falscher Artikel'
    WRONG_QUANTITY = 'wrong_quantity', 'Falsche Menge'
    EXPIRED = 'expired', 'Abgelaufen'
    OTHER = 'other', 'Sonstiges'


class RMAItem(models.Model):
    """Individual item in an RMA."""
    rma = models.ForeignKey(RMA, on_delete=models.CASCADE, related_name='items', verbose_name="RMA")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Produkt")

    # Link to the original receipt item if applicable
    receipt_item = models.ForeignKey(PurchaseOrderReceiptItem, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='rma_items',
                                     verbose_name="Ursprünglicher Wareneingang")

    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Menge")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Stückpreis")

    # Issue details
    issue_type = models.CharField(max_length=20, choices=RMAIssueType.choices,
                                  verbose_name="Problemtyp")
    issue_description = models.TextField(verbose_name="Problembeschreibung")

    # Batch/lot info if applicable
    batch_number = models.CharField(max_length=100, blank=True, verbose_name="Chargennummer")
    serial_number = models.CharField(max_length=100, blank=True, verbose_name="Seriennummer")
    expiry_date = models.DateField(null=True, blank=True, verbose_name="Verfallsdatum")

    # Resolution for this specific item
    is_resolved = models.BooleanField(default=False, verbose_name="Erledigt")
    resolution_notes = models.TextField(blank=True, verbose_name="Lösungsdetails")

    # Item-specific photos or documents
    has_photos = models.BooleanField(default=False, verbose_name="Hat Fotos")

    def __str__(self):
        return f"{self.product.name} ({self.quantity} {self.product.unit})"

    @property
    def value(self):
        if self.quantity is not None and self.unit_price is not None:
            return self.quantity * self.unit_price
        return None

    @property
    def currency(self):
        try:
            sp = self.product.supplier_products.get(supplier=self.rma.supplier)
            return sp.currency or self.rma.supplier.default_currency
        except SupplierProduct.DoesNotExist:
            return self.rma.supplier.default_currency

    class Meta:
        verbose_name = "RMA-Position"
        verbose_name_plural = "RMA-Positionen"


class RMAPhoto(models.Model):
    """Photos documenting the issue with an RMA item."""
    rma_item = models.ForeignKey(RMAItem, on_delete=models.CASCADE, related_name='photos',
                                 verbose_name="RMA-Position")
    image = models.ImageField(upload_to='rma_photos/', verbose_name="Bild")
    caption = models.CharField(max_length=255, blank=True, verbose_name="Bildunterschrift")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Hochgeladen am")

    def __str__(self):
        return f"Foto für {self.rma_item.product.name}"

    class Meta:
        verbose_name = "RMA-Foto"
        verbose_name_plural = "RMA-Fotos"


class RMAHistory(models.Model):
    """History of status changes and actions for an RMA."""
    rma = models.ForeignKey(RMA, on_delete=models.CASCADE, related_name='history',
                            verbose_name="RMA")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Zeitstempel")
    status_from = models.CharField(max_length=20, choices=RMAStatus.choices, null=True, blank=True,
                                   verbose_name="Status vorher")
    status_to = models.CharField(max_length=20, choices=RMAStatus.choices, null=True, blank=True,
                                 verbose_name="Status nachher")
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name="Geändert von")
    note = models.TextField(blank=True, verbose_name="Notiz")

    def __str__(self):
        if self.status_from and self.status_to:
            return f"Status-Änderung: {self.status_from} → {self.status_to}"
        return f"RMA-Ereignis: {self.note}"

    class Meta:
        verbose_name = "RMA-Verlauf"
        verbose_name_plural = "RMA-Verlauf"
        ordering = ['-timestamp']


class RMAComment(models.Model):
    """User comments on the RMA."""
    rma = models.ForeignKey(RMA, on_delete=models.CASCADE, related_name='comments',
                            verbose_name="RMA")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Benutzer")
    comment = models.TextField(verbose_name="Kommentar")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")

    # For attaching files
    attachment = models.FileField(upload_to='rma_attachments/', blank=True, null=True,
                                  verbose_name="Anhang")
    attachment_name = models.CharField(max_length=255, blank=True, verbose_name="Anhangsname")

    # Whether this comment should be visible to the supplier
    is_public = models.BooleanField(default=False,
                                    verbose_name="Öffentlich sichtbar",
                                    help_text="Wenn aktiviert, ist dieser Kommentar auch für den Lieferanten sichtbar")

    def __str__(self):
        return f"Kommentar von {self.user.username} am {self.created_at.strftime('%d.%m.%Y %H:%M')}"

    class Meta:
        verbose_name = "RMA-Kommentar"
        verbose_name_plural = "RMA-Kommentare"
        ordering = ['-created_at']


class RMADocument(models.Model):
    """Documents related to an RMA process."""
    rma = models.ForeignKey(RMA, on_delete=models.CASCADE, related_name='documents',
                            verbose_name="RMA")
    document_type = models.CharField(max_length=50, verbose_name="Dokumenttyp",
                                     choices=[
                                         ('shipping_label', 'Versandetikett'),
                                         ('return_auth', 'Rücksendeerlaubnis'),
                                         ('supplier_response', 'Lieferantenantwort'),
                                         ('credit_note', 'Gutschrift'),
                                         ('other', 'Sonstiges')
                                     ])
    file = models.FileField(upload_to='rma_documents/', verbose_name="Datei")
    title = models.CharField(max_length=255, verbose_name="Titel")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Hochgeladen von")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Hochgeladen am")
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "RMA-Dokument"
        verbose_name_plural = "RMA-Dokumente"
        ordering = ['-uploaded_at']