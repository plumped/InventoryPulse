from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from master_data.models.currency import Currency
from product_management.models.products import Product


class Supplier(models.Model):
    """Model for suppliers."""
    name = models.CharField(max_length=200)
    # Diese Felder beibehalten für Abwärtskompatibilität, aber als deprecated markieren
    contact_person = models.CharField(max_length=100, blank=True,
                                      help_text="Deprecated - Bitte Kontaktpersonen-Modell verwenden")
    email = models.EmailField(blank=True, help_text="Deprecated - Bitte Kontaktpersonen-Modell verwenden")
    phone = models.CharField(max_length=20, blank=True, help_text="Deprecated - Bitte Kontaktpersonen-Modell verwenden")
    address = models.TextField(blank=True, help_text="Deprecated - Bitte Adressen-Modell verwenden")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    website = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Behalten Sie bestehende Felder bei
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        verbose_name="Versandkosten")
    minimum_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                              verbose_name="Mindestbestellwert")
    default_currency = models.ForeignKey('master_data.Currency', on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         verbose_name="Standardwährung",
                                         related_name='suppliers')

    def __str__(self):
        return self.name

    def get_default_address(self, address_type='billing'):
        """Gibt die Standardadresse für den angegebenen Adresstyp zurück."""
        try:
            return self.addresses.get(address_type=address_type, is_default=True)
        except SupplierAddress.DoesNotExist:
            # Fallback auf erste Adresse dieses Typs
            addresses = self.addresses.filter(address_type=address_type)
            if addresses.exists():
                return addresses.first()
            # Fallback auf allgemeine Standardadresse
            addresses = self.addresses.filter(is_default=True)
            if addresses.exists():
                return addresses.first()
            # Fallback auf beliebige Adresse
            if self.addresses.exists():
                return self.addresses.first()
            return None

    def get_default_contact(self, contact_type='general'):
        """Gibt den Standardkontakt für den angegebenen Kontakttyp zurück."""
        try:
            return self.contacts.get(contact_type=contact_type, is_default=True)
        except SupplierContact.DoesNotExist:
            # Fallback auf ersten Kontakt dieses Typs
            contacts = self.contacts.filter(contact_type=contact_type)
            if contacts.exists():
                return contacts.first()
            # Fallback auf allgemeinen Standardkontakt
            contacts = self.contacts.filter(is_default=True)
            if contacts.exists():
                return contacts.first()
            # Fallback auf beliebigen Kontakt
            if self.contacts.exists():
                return self.contacts.first()
            return None

    def get_rma_address(self):
        """Gibt die RMA-Adresse zurück."""
        return self.get_default_address(address_type='rma')

    def get_rma_contact(self):
        """Gibt den RMA-Kontakt zurück."""
        return self.get_default_contact(contact_type='rma')

    def save(self, *args, **kwargs):
        # Wenn keine Standardwährung gesetzt ist, setze die Systemstandardwährung
        if not self.default_currency:
            self.default_currency = Currency.get_default_currency()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['name']


class SupplierProduct(models.Model):
    """Model for linking products to suppliers with additional information."""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='supplier_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='supplier_products')
    supplier_sku = models.CharField(max_length=50, blank=True, verbose_name="Supplier SKU")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Währung als optionales Override für die Lieferanten-Standardwährung
    currency = models.ForeignKey('master_data.Currency', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="Währung", related_name='supplier_products')

    lead_time_days = models.IntegerField(default=7)
    is_preferred = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.supplier.name} - {self.product.name}"

    @property
    def effective_currency(self):
        """Gibt die effektive Währung zurück - entweder die spezifische Währung dieser Produktzuordnung
        oder die Standardwährung des Lieferanten."""
        if self.currency:
            return self.currency
        elif self.supplier and self.supplier.default_currency:
            return self.supplier.default_currency
        else:
            return Currency.get_default_currency()

    class Meta:
        unique_together = ('supplier', 'product')
        ordering = ['supplier', 'product']


# In suppliers/models.py - Add these models for supplier performance tracking

class SupplierPerformanceMetric(models.Model):
    """Model for supplier performance metric definitions."""
    METRIC_TYPES = [
        ('on_time_delivery', 'On-Time Delivery'),
        ('order_accuracy', 'Order Accuracy'),
        ('price_consistency', 'Price Consistency'),
        ('quality', 'Product Quality'),
        ('responsiveness', 'Responsiveness'),
        ('custom', 'Custom Metric'),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False, help_text="System metrics cannot be deleted")
    weight = models.IntegerField(default=1, help_text="Weight for calculating composite scores")
    target_value = models.DecimalField(max_digits=5, decimal_places=2, default=100.00,
                                       help_text="Target value in percent (100% is perfect)")
    minimum_value = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Performance Metric"
        verbose_name_plural = "Performance Metrics"


class SupplierPerformance(models.Model):
    """Model for tracking supplier performance over time."""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='performance_records')
    metric = models.ForeignKey(SupplierPerformanceMetric, on_delete=models.CASCADE)
    value = models.DecimalField(max_digits=5, decimal_places=2,
                                help_text="Performance value in percent (100% is perfect)")
    evaluation_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)
    evaluated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='supplier_evaluations')
    evaluation_period_start = models.DateField(null=True, blank=True)
    evaluation_period_end = models.DateField(null=True, blank=True)
    reference_orders = models.ManyToManyField('order.PurchaseOrder', blank=True, related_name='performance_evaluations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.supplier.name} - {self.metric.name} ({self.evaluation_date})"

    class Meta:
        ordering = ['-evaluation_date', 'supplier']
        verbose_name = "Supplier Performance"
        verbose_name_plural = "Supplier Performances"
        # Make sure we don't have duplicates for the same supplier, metric and date
        unique_together = ['supplier', 'metric', 'evaluation_date']


class SupplierPerformanceCalculator:
    """Utility class to calculate supplier performance metrics."""

    @classmethod
    def calculate_on_time_delivery(cls, supplier, start_date=None, end_date=None):
        """Calculate on-time delivery performance."""
        from order.models import PurchaseOrder

        # Default to last 90 days if no dates specified
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=90)

        # Get completed orders for this supplier in the date range
        orders = PurchaseOrder.objects.filter(
            supplier=supplier,
            status__in=['received', 'partially_received'],
            order_date__gte=start_date,
            order_date__lte=end_date
        )

        if not orders.exists():
            return None, []

        on_time_count = 0
        relevant_orders = []

        for order in orders:
            # Only consider orders with expected_delivery date
            if not order.expected_delivery:
                continue

            relevant_orders.append(order)

            # Get the date of the first receipt
            first_receipt_date = order.receipts.order_by('receipt_date').values_list('receipt_date', flat=True).first()

            if first_receipt_date and first_receipt_date <= order.expected_delivery:
                on_time_count += 1

        # Calculate percentage
        if relevant_orders:
            percentage = (on_time_count / len(relevant_orders)) * 100
            return round(percentage, 2), relevant_orders
        else:
            return None, []

    @classmethod
    def calculate_order_accuracy(cls, supplier, start_date=None, end_date=None):
        """Calculate order accuracy based on received quantities matching ordered quantities."""
        from order.models import PurchaseOrder

        # Default to last 90 days if no dates specified
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=90)

        # Get completed orders for this supplier in the date range
        orders = PurchaseOrder.objects.filter(
            supplier=supplier,
            status__in=['received', 'partially_received'],
            order_date__gte=start_date,
            order_date__lte=end_date
        )

        if not orders.exists():
            return None, []

        total_order_items = 0
        correct_items = 0
        relevant_orders = []

        for order in orders:
            has_receipts = order.receipts.exists()
            if not has_receipts:
                continue

            relevant_orders.append(order)

            for item in order.items.all():
                total_order_items += 1

                # Check if received quantity matches ordered quantity
                if item.quantity_received == item.quantity_ordered:
                    correct_items += 1

        # Calculate percentage
        if total_order_items > 0:
            percentage = (correct_items / total_order_items) * 100
            return round(percentage, 2), relevant_orders
        else:
            return None, []

    @classmethod
    def calculate_price_consistency(cls, supplier, start_date=None, end_date=None):
        """Calculate price consistency based on price variations for the same products."""
        from django.db.models import Avg, StdDev

        # Print the start of the calculation
        print(f"\n=== Price consistency calculation for supplier: {supplier.name} ===")
        print(f"Date range: {start_date} to {end_date}")

        # Default to last 90 days if no dates specified
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=90)

        # Get all supplier products
        supplier_products = supplier.supplier_products.all()
        print(f"Found {supplier_products.count()} products for supplier")

        if not supplier_products.exists():
            print("No supplier products found, returning None")
            return None, []

        # Get all order items for this supplier's products in the date range
        from order.models import PurchaseOrderItem, PurchaseOrder

        relevant_orders = PurchaseOrder.objects.filter(
            supplier=supplier,
            order_date__gte=start_date,
            order_date__lte=end_date
        )
        print(f"Found {relevant_orders.count()} relevant orders in date range")

        # Calculate price variation score
        variation_scores = []
        products_analyzed = 0

        for sp in supplier_products:
            print(f"\nAnalyzing product: {sp.product.name} (ID: {sp.product.id})")

            # Get all order items for this product
            order_items = PurchaseOrderItem.objects.filter(
                purchase_order__in=relevant_orders,
                product=sp.product
            )

            print(f"  Found {order_items.count()} order items for this product")

            if order_items.count() < 2:  # Need at least 2 orders to calculate variation
                print(f"  Skipping product - less than 2 orders ({order_items.count()})")
                continue

            # Print all prices to see the raw data
            print("  Price values:")
            for item in order_items:
                print(f"    Order {item.purchase_order.order_number}: {item.unit_price}")

            # Calculate coefficient of variation (standard deviation / mean)
            stats = order_items.aggregate(
                avg_price=Avg('unit_price'),
                stddev_price=StdDev('unit_price')
            )

            avg_price = stats['avg_price'] or 0
            stddev_price = stats['stddev_price'] or 0

            print(f"  Stats - Avg price: {avg_price}, StdDev: {stddev_price}")

            if avg_price > 0:
                cv = (stddev_price / avg_price) * 100  # As percentage
                print(f"  Coefficient of variation: {cv}%")

                # Add a tolerance threshold for very small variations
                if stddev_price < 0.0001:
                    print("  StdDev is very small, setting variation_score to 100")
                    variation_score = 100
                else:
                    variation_score = max(0, 100 - (cv * 2))


                print(f"  Variation score: {variation_score}")

                variation_scores.append(variation_score)
                products_analyzed += 1
            else:
                print("  Average price is zero, skipping product")

        # Calculate average score
        print(f"\nTotal products analyzed: {products_analyzed}")
        print(f"Variation scores: {variation_scores}")

        if variation_scores:
            avg_score = sum(variation_scores) / len(variation_scores)
            print(f"Final average score: {avg_score}")
            return round(avg_score, 2), list(relevant_orders)
        else:
            print("No variation scores calculated, returning None")
            # Add fallback for when no variation could be calculated but we have products
            if supplier_products.exists() and relevant_orders.exists():
                print("Products and orders exist but no scores calculated - assuming perfect consistency (100%)")
                return 100.0, list(relevant_orders)
            return None, []

    # Füge diese Methode zur SupplierPerformanceCalculator-Klasse in suppliers/models.py hinzu

    @classmethod
    def calculate_rma_quality(cls, supplier, start_date=None, end_date=None):
        """
        Berechnet die Qualitätsrate basierend auf RMAs im Verhältnis zu Bestellungen.

        Ein niedrigerer Prozentsatz von RMAs im Vergleich zu erhaltenen Bestellungen
        führt zu einer höheren Qualitätsbewertung.

        Returns:
            tuple: (quality_score, relevant_orders)
                - quality_score: Prozentsatz (0-100) der Qualitätsbewertung
                - relevant_orders: Liste der relevanten Bestellungen
        """
        from django.db.models import Sum
        from order.models import PurchaseOrder, PurchaseOrderItem
        from rma.models import RMA, RMAStatus, RMAItem, RMAIssueType

        # Default auf die letzten 90 Tage, wenn keine Daten angegeben sind
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=90)

        # Hole alle empfangenen Bestellungen für diesen Lieferanten im Zeitraum
        orders = PurchaseOrder.objects.filter(
            supplier=supplier,
            status__in=['received', 'partially_received', 'received_with_issues'],
            receipts__receipt_date__gte=start_date,
            receipts__receipt_date__lte=end_date
        ).distinct()

        if not orders.exists():
            return None, []

        # Gesamtwert und Anzahl der Bestellungen
        order_count = orders.count()
        total_order_items = PurchaseOrderItem.objects.filter(purchase_order__in=orders).count()

        try:
            total_order_value = sum(order.total_amount for order in orders)
        except:
            # Fallback, falls total_amount nicht für alle Bestellungen verfügbar ist
            total_order_value = PurchaseOrderItem.objects.filter(
                purchase_order__in=orders
            ).aggregate(
                total=Sum('quantity_ordered') * Sum('unit_price')
            )['total'] or 0

        # RMAs für diese Bestellungen im gleichen Zeitraum
        rmas = RMA.objects.filter(
            supplier=supplier,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status__in=[
                RMAStatus.PENDING,
                RMAStatus.APPROVED,
                RMAStatus.SENT,
                RMAStatus.RESOLVED
            ]
        ).exclude(status__in=[RMAStatus.DRAFT, RMAStatus.CANCELLED])

        # Gesamtmenge und Wert der RMA-Positionen
        rma_items = RMAItem.objects.filter(rma__in=rmas)
        rma_item_count = rma_items.count()
        rma_value = sum(item.value or 0 for item in rma_items)

        # RMAs nach Problemtyp gruppieren und gewichten
        # Defekte oder beschädigte Artikel sind schwerwiegender als Lieferfehler
        severity_weights = {
            RMAIssueType.DEFECTIVE: 1.0,  # Defekt: volle Gewichtung
            RMAIssueType.DAMAGED: 0.8,  # Beschädigt: 80% Gewichtung
            RMAIssueType.EXPIRED: 0.7,  # Abgelaufen: 70% Gewichtung
            RMAIssueType.WRONG_ITEM: 0.6,  # Falscher Artikel: 60% Gewichtung
            RMAIssueType.WRONG_QUANTITY: 0.5,  # Falsche Menge: 50% Gewichtung
            RMAIssueType.OTHER: 0.7  # Sonstiges: 70% Gewichtung
        }

        # Gewichtete Anzahl von RMA-Positionen berechnen
        weighted_rma_items = 0
        for issue_type, weight in severity_weights.items():
            type_count = rma_items.filter(issue_type=issue_type).count()
            weighted_rma_items += type_count * weight

        # Mehrere Faktoren für die Bewertung berücksichtigen

        # Faktor 1: Verhältnis von RMAs zu Bestellungen
        if order_count > 0:
            rma_order_ratio = rmas.count() / order_count
        else:
            rma_order_ratio = 0

        # Faktor 2: Verhältnis von RMA-Positionen zu Bestellpositionen
        if total_order_items > 0:
            rma_item_ratio = weighted_rma_items / total_order_items
        else:
            rma_item_ratio = 0

        # Faktor 3: Verhältnis von RMA-Wert zu Bestellwert
        if total_order_value > 0:
            rma_value_ratio = rma_value / total_order_value
        else:
            rma_value_ratio = 0

        # Kombinierter Score (niedrigere Raten sind besser)
        # Die verschiedenen Faktoren werden gewichtet
        combined_ratio = (
                float(rma_order_ratio) * 0.3 +
                float(rma_item_ratio) * 0.5 +
                float(rma_value_ratio) * 0.2
        )

        # Umwandlung in eine Qualitätsbewertung (0-100%)
        # Wenn combined_ratio = 0, ist die Qualität 100%
        # Wenn combined_ratio >= 0.3 (30% Probleme), ist die Qualität 0%
        if combined_ratio >= 0.3:
            quality_score = 0
        else:
            quality_score = 100 - (combined_ratio * (100 / 0.3))  # Linear abfallend von 100% bis 0%

        return round(quality_score, 2), list(orders)

    @classmethod
    def calculate_all_metrics(cls, supplier, start_date=None, end_date=None, save_results=True):
        """Calculate all performance metrics for a supplier and optionally save them."""
        results = {}

        # Calculate on-time delivery
        on_time_score, on_time_orders = cls.calculate_on_time_delivery(supplier, start_date, end_date)
        results['on_time_delivery'] = {'score': on_time_score, 'orders': on_time_orders}

        # Calculate order accuracy
        accuracy_score, accuracy_orders = cls.calculate_order_accuracy(supplier, start_date, end_date)
        results['order_accuracy'] = {'score': accuracy_score, 'orders': accuracy_orders}

        # Calculate price consistency
        consistency_score, consistency_orders = cls.calculate_price_consistency(supplier, start_date, end_date)
        results['price_consistency'] = {'score': consistency_score, 'orders': consistency_orders}

        # Calculate RMA quality
        quality_score, quality_orders = cls.calculate_rma_quality(supplier, start_date, end_date)
        results['product_quality'] = {'score': quality_score, 'orders': quality_orders}

        # Save the results if requested
        if save_results:
            try:
                # Get or create the metrics
                on_time_metric, _ = SupplierPerformanceMetric.objects.get_or_create(
                    code='on_time_delivery',
                    defaults={
                        'name': 'On-Time Delivery',
                        'description': 'Percentage of orders delivered on or before the expected delivery date',
                        'metric_type': 'on_time_delivery',
                        'is_system': True
                    }
                )

                accuracy_metric, _ = SupplierPerformanceMetric.objects.get_or_create(
                    code='order_accuracy',
                    defaults={
                        'name': 'Order Accuracy',
                        'description': 'Percentage of order items that were delivered with the correct quantity',
                        'metric_type': 'order_accuracy',
                        'is_system': True
                    }
                )

                consistency_metric, _ = SupplierPerformanceMetric.objects.get_or_create(
                    code='price_consistency',
                    defaults={
                        'name': 'Price Consistency',
                        'description': 'Consistency of pricing for the same products over time',
                        'metric_type': 'price_consistency',
                        'is_system': True
                    }
                )

                quality_metric, _ = SupplierPerformanceMetric.objects.get_or_create(
                    code='product_quality',
                    defaults={
                        'name': 'Product Quality',
                        'description': 'Product quality based on the rate of RMAs (Return Merchandise Authorizations)',
                        'metric_type': 'quality',
                        'is_system': True
                    }
                )

                # Save the performance records
                today = timezone.now().date()

                if on_time_score is not None:
                    perf, created = SupplierPerformance.objects.update_or_create(
                        supplier=supplier,
                        metric=on_time_metric,
                        evaluation_date=today,
                        defaults={
                            'value': on_time_score,
                            'evaluation_period_start': start_date,
                            'evaluation_period_end': end_date,
                            'notes': f'Automatically calculated based on {len(on_time_orders)} orders'
                        }
                    )
                    if on_time_orders and created:
                        perf.reference_orders.set(on_time_orders)

                if accuracy_score is not None:
                    perf, created = SupplierPerformance.objects.update_or_create(
                        supplier=supplier,
                        metric=accuracy_metric,
                        evaluation_date=today,
                        defaults={
                            'value': accuracy_score,
                            'evaluation_period_start': start_date,
                            'evaluation_period_end': end_date,
                            'notes': f'Automatically calculated based on {len(accuracy_orders)} orders'
                        }
                    )
                    if accuracy_orders and created:
                        perf.reference_orders.set(accuracy_orders)

                if consistency_score is not None:
                    perf, created = SupplierPerformance.objects.update_or_create(
                        supplier=supplier,
                        metric=consistency_metric,
                        evaluation_date=today,
                        defaults={
                            'value': consistency_score,
                            'evaluation_period_start': start_date,
                            'evaluation_period_end': end_date,
                            'notes': f'Automatically calculated based on {len(consistency_orders)} orders'
                        }
                    )
                    if consistency_orders and created:
                        perf.reference_orders.set(consistency_orders)

                if quality_score is not None:
                    perf, created = SupplierPerformance.objects.update_or_create(
                        supplier=supplier,
                        metric=quality_metric,
                        evaluation_date=today,
                        defaults={
                            'value': quality_score,
                            'evaluation_period_start': start_date,
                            'evaluation_period_end': end_date,
                            'notes': f'Automatically calculated based on RMA rate for {len(quality_orders)} orders'
                        }
                    )
                    if quality_orders and created:
                        perf.reference_orders.set(quality_orders)

            except Exception as e:
                # Log the error but don't re-raise
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error saving performance metrics for {supplier}: {e}")

        return results


class AddressType(models.TextChoices):
    """Typen von Adressen, die ein Lieferant haben kann."""
    BILLING = 'billing', 'Rechnungsadresse'
    SHIPPING = 'shipping', 'Lieferadresse'
    RMA = 'rma', 'RMA-Rücksendeadresse'
    WAREHOUSE = 'warehouse', 'Lageradresse'
    OFFICE = 'office', 'Büro'
    OTHER = 'other', 'Sonstige'


class SupplierAddress(models.Model):
    """Modell für verschiedene Adressen eines Lieferanten."""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=20, choices=AddressType.choices, default=AddressType.BILLING)
    is_default = models.BooleanField(default=False, verbose_name="Standardadresse für diesen Typ")
    name = models.CharField(max_length=200, blank=True, verbose_name="Adressname")
    street = models.CharField(max_length=200, verbose_name="Straße")
    street_number = models.CharField(max_length=20, blank=True, verbose_name="Hausnummer")
    postal_code = models.CharField(max_length=20, verbose_name="PLZ")
    city = models.CharField(max_length=100, verbose_name="Stadt")
    state = models.CharField(max_length=100, blank=True, verbose_name="Bundesland/Region")
    country = models.CharField(max_length=100, verbose_name="Land")
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_address_type_display()})" if self.name else f"{self.get_address_type_display()}: {self.street}, {self.city}"

    def full_address(self):
        """Gibt die vollständige formatierte Adresse zurück."""
        address_parts = []
        if self.name:
            address_parts.append(self.name)

        street_line = self.street
        if self.street_number:
            street_line += " " + self.street_number
        address_parts.append(street_line)

        city_line = f"{self.postal_code} {self.city}"
        address_parts.append(city_line)

        if self.state:
            address_parts.append(self.state)

        address_parts.append(self.country)

        return "\n".join(address_parts)

    class Meta:
        verbose_name = "Lieferantenadresse"
        verbose_name_plural = "Lieferantenadressen"
        ordering = ['supplier', 'address_type', '-is_default']
        # Sicherstellen, dass es nur eine Standardadresse pro Adresstyp gibt
        constraints = [
            models.UniqueConstraint(
                fields=['supplier', 'address_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_address_per_type'
            )
        ]


class ContactType(models.TextChoices):
    """Typen von Kontaktpersonen bei einem Lieferanten."""
    GENERAL = 'general', 'Allgemeiner Kontakt'
    SALES = 'sales', 'Vertrieb'
    SUPPORT = 'support', 'Support'
    ACCOUNTING = 'accounting', 'Buchhaltung'
    RMA = 'rma', 'RMA/Reklamationen'
    TECHNICAL = 'technical', 'Technischer Kontakt'
    MANAGEMENT = 'management', 'Geschäftsführung'
    OTHER = 'other', 'Sonstiger Kontakt'


class SupplierContact(models.Model):
    """Modell für verschiedene Kontaktpersonen eines Lieferanten."""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='contacts')
    contact_type = models.CharField(max_length=20, choices=ContactType.choices, default=ContactType.GENERAL)
    is_default = models.BooleanField(default=False, verbose_name="Standardkontakt für diesen Typ")
    title = models.CharField(max_length=50, blank=True, verbose_name="Titel/Anrede")
    first_name = models.CharField(max_length=100, verbose_name="Vorname")
    last_name = models.CharField(max_length=100, verbose_name="Nachname")
    position = models.CharField(max_length=100, blank=True, verbose_name="Position/Abteilung")
    email = models.EmailField(blank=True, verbose_name="E-Mail")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Telefon")
    mobile = models.CharField(max_length=50, blank=True, verbose_name="Mobiltelefon")
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_contact_type_display()})"

    def full_name(self):
        """Gibt den vollständigen Namen inklusive Titel zurück."""
        if self.title:
            return f"{self.title} {self.first_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "Kontaktperson"
        verbose_name_plural = "Kontaktpersonen"
        ordering = ['supplier', 'contact_type', '-is_default', 'last_name']
        # Sicherstellen, dass es nur einen Standardkontakt pro Kontakttyp gibt
        constraints = [
            models.UniqueConstraint(
                fields=['supplier', 'contact_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_contact_per_type'
            )
        ]