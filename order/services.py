# order/services.py
from decimal import Decimal
from django.db.models import Sum, F, Case, When, Value, Q
from core.models import Product, ProductWarehouse
from suppliers.models import SupplierProduct
from .models import OrderSuggestion


def generate_order_suggestions():
    """Generiere Bestellvorschläge für Produkte mit kritischem Bestand"""
    # Produkte mit kritischem Bestand identifizieren
    products_with_low_stock = Product.objects.annotate(
        total_stock=Sum('productwarehouse__quantity'),
    ).filter(
        Q(total_stock__lt=F('minimum_stock')) | Q(total_stock__isnull=True)
    )

    # Löschen der alten Vorschläge
    OrderSuggestion.objects.all().delete()

    # Neue Vorschläge erstellen
    suggestions = []

    for product in products_with_low_stock:
        # Aktuellen Bestand abrufen
        current_stock = product.total_stock or Decimal('0')

        # Optimale Bestellmenge berechnen (nimm das Maximum: entweder minimum_stock+20% oder bisher fehlende Menge*2)
        target_stock = max(
            product.minimum_stock * Decimal('1.2'),
            product.minimum_stock * Decimal('2') - current_stock
        )

        # Bestellmenge = Zielmenge - aktueller Bestand
        suggested_quantity = max(target_stock - current_stock, Decimal('0'))

        # Aufrunden auf ganze Einheiten
        suggested_quantity = suggested_quantity.quantize(Decimal('1'))

        # Wenn nichts zu bestellen ist, überspringe
        if suggested_quantity <= 0:
            continue

        # Bevorzugten Lieferanten ermitteln
        preferred_supplier = None
        try:
            # Versuche, den bevorzugten Lieferanten zu finden
            supplier_product = SupplierProduct.objects.filter(
                product=product,
                is_preferred=True
            ).first()

            if supplier_product:
                preferred_supplier = supplier_product.supplier
            else:
                # Fallback: Nimm den ersten verfügbaren Lieferanten
                supplier_product = SupplierProduct.objects.filter(
                    product=product
                ).first()

                if supplier_product:
                    preferred_supplier = supplier_product.supplier
        except:
            pass

        # Bestellvorschlag erstellen
        suggestion = OrderSuggestion(
            product=product,
            current_stock=current_stock,
            minimum_stock=product.minimum_stock,
            suggested_order_quantity=suggested_quantity,
            preferred_supplier=preferred_supplier
        )
        suggestions.append(suggestion)

    # Bulk-Insert der Vorschläge
    if suggestions:
        OrderSuggestion.objects.bulk_create(suggestions)

    return len(suggestions)