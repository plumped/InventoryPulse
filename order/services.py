from django.db.models import Sum, F, Q, Exists, OuterRef
from decimal import Decimal
from core.models import Product, ProductWarehouse
from suppliers.models import SupplierProduct
from .models import OrderSuggestion, PurchaseOrder, PurchaseOrderItem


# Korrigierte Version der generate_order_suggestions-Funktion

def generate_order_suggestions():
    """Generiere Bestellvorschläge für Produkte mit kritischem Bestand,
    unter Berücksichtigung bestehender Bestellungen."""


    # Unterabfrage für Produkte, die bereits in aktiven Bestellungen sind
    products_in_orders = PurchaseOrderItem.objects.filter(
        product=OuterRef('pk'),
        purchase_order__status__in=['draft', 'pending', 'approved', 'sent']
    )

    # Produkte mit kritischem Bestand identifizieren, die NICHT bereits bestellt sind
    products_with_low_stock = Product.objects.annotate(
        computed_total_stock=Sum('productwarehouse__quantity'),
        has_pending_orders=Exists(products_in_orders)
    ).filter(
        (Q(computed_total_stock__lt=F('minimum_stock')) |
         Q(computed_total_stock__isnull=True, minimum_stock__gt=0)) &
        Q(has_pending_orders=False)
    )

    # Alternativ: Produkte mit kritischem Bestand identifizieren und
    # später die zu bestellende Menge um bereits bestellte Mengen reduzieren
    # Diese Variante ist besser, wenn vorhandene Bestellungen berücksichtigt
    # werden sollen, aber möglicherweise weitere Mengen bestellt werden müssen

    # Produkte mit kritischem Bestand, inklusive derer mit laufenden Bestellungen
    all_low_stock_products = Product.objects.annotate(
        computed_total_stock=Sum('productwarehouse__quantity')
    ).filter(
        Q(computed_total_stock__lt=F('minimum_stock')) |
        Q(computed_total_stock__isnull=True, minimum_stock__gt=0)
    )

    # Löschen der alten Vorschläge
    OrderSuggestion.objects.all().delete()

    # Neue Vorschläge erstellen
    suggestions = []

    for product in all_low_stock_products:
        # Aktuellen Bestand abrufen
        current_stock = product.productwarehouse_set.aggregate(
            total=Sum('quantity')
        )['total'] or Decimal('0')

        # Bestehende Bestellungen für dieses Produkt abrufen
        already_ordered_quantity = PurchaseOrderItem.objects.filter(
            product=product,
            purchase_order__status__in=['draft', 'pending', 'approved', 'sent']
        ).aggregate(
            total=Sum('quantity_ordered')
        )['total'] or Decimal('0')

        # Gesamtmenge im System (Bestand + bereits bestellt)
        total_system_quantity = current_stock + already_ordered_quantity

        # Wenn bereits genug bestellt wurde, kein Vorschlag
        if total_system_quantity >= product.minimum_stock:
            continue

        # Optimale Bestellmenge berechnen unter Berücksichtigung bereits bestellter Mengen
        target_stock = max(
            product.minimum_stock * Decimal('1.2'),
            product.minimum_stock * Decimal('2') - current_stock
        )

        # Bestellmenge = Zielmenge - (aktueller Bestand + bereits bestellt)
        suggested_quantity = max(target_stock - total_system_quantity, Decimal('0'))

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


# In order/services.py - Erstellen Sie eine neue Funktion, die Bestellvorschläge aktualisiert

def update_order_suggestions_suppliers():
    """Aktualisiert die bevorzugten Lieferanten für alle Bestellvorschläge basierend
    auf den aktuellen Lieferanten-Produkt-Zuordnungen."""

    from suppliers.models import SupplierProduct

    # Alle Bestellvorschläge ohne bevorzugten Lieferanten abrufen
    suggestions_without_supplier = OrderSuggestion.objects.filter(preferred_supplier__isnull=True)
    updated_count = 0

    for suggestion in suggestions_without_supplier:
        # Versuche, den bevorzugten Lieferanten zu finden
        try:
            # Zuerst nach bevorzugtem Lieferanten suchen
            supplier_product = SupplierProduct.objects.filter(
                product=suggestion.product,
                is_preferred=True
            ).first()

            if not supplier_product:
                # Als Fallback den ersten verfügbaren Lieferanten verwenden
                supplier_product = SupplierProduct.objects.filter(
                    product=suggestion.product
                ).first()

            if supplier_product:
                suggestion.preferred_supplier = supplier_product.supplier
                suggestion.save()
                updated_count += 1
        except Exception:
            # Fehler ignorieren und mit dem nächsten Vorschlag fortfahren
            continue

    return updated_count