from django.db.models.signals import post_save
from django.dispatch import receiver
from inventory.models import StockMovement
from core.models import Product

from .models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseRecommendation
)


@receiver(post_save, sender=GoodsReceipt)
def update_stock_on_goods_receipt(sender, instance, **kwargs):
    """
    When a goods receipt is completed, update inventory levels.
    """
    if instance.status == 'completed':
        # Process each receipt item
        for receipt_item in instance.items.all():
            if receipt_item.received_quantity > 0 and not receipt_item.is_defective:
                # Create stock movement
                StockMovement.objects.create(
                    product=receipt_item.purchase_order_item.product,
                    quantity=receipt_item.received_quantity,
                    movement_type='in',
                    reference=f'Wareneingang {instance.receipt_number}',
                    notes=f'Aus Bestellung {instance.purchase_order.order_number}',
                    created_by=instance.created_by
                )


@receiver(post_save, sender=Product)
def check_stock_level(sender, instance, **kwargs):
    """
    Check if stock is below minimum and create purchase recommendation.
    """
    # Skip if current stock is above minimum
    if instance.current_stock > instance.minimum_stock:
        # Check if there are any active recommendations and mark them as ignored
        PurchaseRecommendation.objects.filter(
            product=instance,
            status='new'
        ).update(status='ignored')
        return

    # Calculate recommended quantity
    # Default formula: twice the minimum stock minus current stock
    recommended_quantity = (instance.minimum_stock * 2) - instance.current_stock

    # Find preferred supplier
    supplier_product = instance.supplier_products.filter(is_preferred=True).first()
    if not supplier_product:
        # If no preferred supplier, get the first one
        supplier_product = instance.supplier_products.first()

    # Check for existing recommendations
    existing_rec = PurchaseRecommendation.objects.filter(
        product=instance,
        status__in=['new', 'in_process']
    ).first()

    if existing_rec:
        # Update existing recommendation
        existing_rec.current_stock = instance.current_stock
        existing_rec.min_stock = instance.minimum_stock
        existing_rec.recommended_quantity = recommended_quantity
        existing_rec.supplier_product = supplier_product
        existing_rec.save()
    else:
        # Create new recommendation
        PurchaseRecommendation.objects.create(
            product=instance,
            supplier_product=supplier_product,
            current_stock=instance.current_stock,
            min_stock=instance.minimum_stock,
            recommended_quantity=recommended_quantity
        )