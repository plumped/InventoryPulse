from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import models
from core.models import Product


class Supplier(models.Model):
    """Model for suppliers."""
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # Neue Felder hinzufügen
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        verbose_name="Versandkosten")
    minimum_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                              verbose_name="Mindestbestellwert")

    # Standard-Währung für diesen Lieferanten
    default_currency = models.ForeignKey('core.Currency', on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         verbose_name="Standardwährung",
                                         related_name='suppliers')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Wenn keine Standardwährung gesetzt ist, setze die Systemstandardwährung
        if not self.default_currency:
            from core.models import Currency
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
    currency = models.ForeignKey('core.Currency', on_delete=models.SET_NULL, null=True, blank=True,
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
            from core.models import Currency
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

            except Exception as e:
                # Log the error but don't re-raise
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error saving performance metrics for {supplier}: {e}")

        return results