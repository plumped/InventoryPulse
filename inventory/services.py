from django.db import transaction
from django.db.models import F
from core.models import Product
from .models import StockMovement


@transaction.atomic
def update_product_stock(product_id, quantity, movement_type, user, reference="", notes=""):
    """
    Aktualisiert den Lagerbestand eines Produkts und erstellt einen Bewegungseintrag.

    Args:
        product_id: ID des Produkts
        quantity: Menge der Bewegung
        movement_type: Art der Bewegung ('in', 'out', 'adj')
        user: Benutzer, der die Bewegung durchführt
        reference: Optionale Referenz (z.B. Lieferschein-Nr.)
        notes: Optionale Bemerkungen

    Returns:
        StockMovement: Der erstellte Bewegungseintrag

    Raises:
        ValueError: Wenn nicht genügend Lagerbestand für einen Abgang vorhanden ist
    """
    # Produkt mit Sperre für Updates laden
    product = Product.objects.select_for_update().get(id=product_id)

    if movement_type == 'in':
        # Bestandszugang
        product.current_stock += quantity
    elif movement_type == 'out':
        # Bestandsabgang
        if product.current_stock < quantity:
            raise ValueError(f"Nicht genügend Lagerbestand verfügbar. Aktueller Bestand: {product.current_stock}")
        product.current_stock -= quantity
    elif movement_type == 'adj':
        # Bestandskorrektur (setzt Bestand auf angegebene Menge)
        product.current_stock = quantity

    # Produkt speichern
    product.save()

    # Bewegungseintrag erstellen
    movement = StockMovement.objects.create(
        product=product,
        quantity=quantity,
        movement_type=movement_type,
        reference=reference,
        notes=notes,
        created_by=user
    )

    return movement


def check_low_stock_products():
    """
    Überprüft alle Produkte auf kritischen Bestand.

    Returns:
        list: Liste von Produkten mit kritischem Bestand
    """
    return Product.objects.filter(current_stock__lte=F('minimum_stock')).order_by('name')