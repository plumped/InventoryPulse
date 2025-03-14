from datetime import datetime
from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models
from django.db.models import F
from organization.models import Department


class Warehouse(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class StockMovement(models.Model):
    product = models.ForeignKey('core.Product', on_delete=models.CASCADE)  # String-Referenz
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    movement_type = models.CharField(
        max_length=3,
        choices=[
            ('in', 'Eingang'),
            ('out', 'Ausgang'),
            ('adj', 'Anpassung'),
        ]
    )
    reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.product.name} ({self.quantity})"


class StockTake(models.Model):
    """Model for inventory stock take."""
    STATUS_CHOICES = (
        ('draft', 'Entwurf'),
        ('in_progress', 'In Bearbeitung'),
        ('completed', 'Abgeschlossen'),
        ('cancelled', 'Abgebrochen'),
    )

    name = models.CharField(max_length=100, verbose_name="Bezeichnung")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Status")
    start_date = models.DateTimeField(auto_now_add=True, verbose_name="Startdatum")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Enddatum")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='stock_takes_created',
                                   verbose_name="Erstellt von")
    completed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='stock_takes_completed', null=True,
                                     blank=True, verbose_name="Abgeschlossen von")
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    inventory_type = models.CharField(
        max_length=20,
        choices=[
            ('full', 'Komplettinventur'),
            ('rolling', 'Rollierende Inventur'),
            ('blind', 'Blindzählung'),
            ('sample', 'Stichprobeninventur'),
        ],
        default='full',
        verbose_name="Inventurtyp"
    )
    display_expected_quantity = models.BooleanField(
        default=True,
        verbose_name="Erwartete Mengen anzeigen",
        help_text="Wenn deaktiviert, werden den Zählern die erwarteten Mengen nicht angezeigt (Blindzählung)"
    )
    cycle_count_category = models.CharField(
        max_length=1,
        choices=[
            ('A', 'A-Artikel (hoher Wert/Umschlag)'),
            ('B', 'B-Artikel (mittlerer Wert/Umschlag)'),
            ('C', 'C-Artikel (niedriger Wert/Umschlag)'),
            ('', 'Alle Artikel'),
        ],
        blank=True,
        verbose_name="Artikelkategorie für rollierende Inventur"
    )
    count_frequency = models.IntegerField(
        default=0,
        verbose_name="Zählfrequenz in Tagen",
        help_text="0 = einmalige Inventur, >0 = Zyklus in Tagen für rollierende Inventur"
    )
    last_cycle_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Datum der letzten Zykleninventur"
    )

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def get_total_discrepancy(self):
        """Get the total discrepancy amount from this stock take."""
        total = 0
        for item in self.stocktakeitem_set.all():
            total += item.get_discrepancy_value()
        return total

    def get_discrepancy_count(self):
        """Get the count of items with discrepancies."""
        return self.stocktakeitem_set.filter(is_counted=True).exclude(counted_quantity=F('expected_quantity')).count()

    def get_completion_percentage(self):
        """Get the percentage of items counted."""
        total = self.stocktakeitem_set.count()
        if total == 0:
            return 100  # Avoid division by zero
        counted = self.stocktakeitem_set.filter(is_counted=True).count()
        return int((counted / total) * 100)

    def is_blind_count(self):
        """Überprüft, ob es sich um eine Blindzählung handelt."""
        return not self.display_expected_quantity

    def get_next_cycle_date(self):
        """Berechnet das Datum der nächsten Zykleninventur."""
        if not self.count_frequency or not self.last_cycle_date:
            return None
        return self.last_cycle_date + datetime.timedelta(days=self.count_frequency)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Inventur"
        verbose_name_plural = "Inventuren"


class StockTakeItem(models.Model):
    """Model for individual items in a stock take."""
    stock_take = models.ForeignKey(StockTake, on_delete=models.CASCADE, verbose_name="Inventur")
    product = models.ForeignKey('core.Product', on_delete=models.CASCADE, verbose_name="Produkt")
    expected_quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Erwartete Menge")
    counted_quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                           verbose_name="Gezählte Menge")
    is_counted = models.BooleanField(default=False, verbose_name="Gezählt")
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")
    counted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Gezählt von")
    counted_at = models.DateTimeField(null=True, blank=True, verbose_name="Gezählt am")

    def __str__(self):
        return f"{self.product.name} - {self.stock_take.name}"

    def get_discrepancy(self):
        """Get the discrepancy between expected and counted."""
        if not self.is_counted:
            return None
        return self.counted_quantity - self.expected_quantity

    def get_discrepancy_value(self):
        """Get the absolute discrepancy value."""
        discrepancy = self.get_discrepancy()
        if discrepancy is None:
            return 0
        return abs(discrepancy)

    def get_discrepancy_status(self):
        """Get a color status based on the discrepancy."""
        if not self.is_counted:
            return "secondary"  # Not counted yet

        discrepancy = self.get_discrepancy()
        if discrepancy == 0:
            return "success"  # No discrepancy
        elif abs(discrepancy) <= Decimal('0.05') * self.expected_quantity:  # 5% tolerance
            return "warning"  # Small discrepancy
        else:
            return "danger"  # Large discrepancy

    class Meta:
        unique_together = ('stock_take', 'product')
        ordering = ['product__name']
        verbose_name = "Inventurposition"
        verbose_name_plural = "Inventurpositionen"
