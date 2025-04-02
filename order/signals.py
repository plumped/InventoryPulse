from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import PurchaseOrder, PurchaseOrderComment


@receiver(pre_save, sender=PurchaseOrder)
def track_status_changes(sender, instance, **kwargs):
    """
    Track status changes in purchase orders and create comments automatically
    """
    # Skip for new orders
    if not instance.pk:
        return

    try:
        # Get the original order from database to compare
        old_order = PurchaseOrder.objects.get(pk=instance.pk)

        # If status has changed, create a comment
        if old_order.status != instance.status:
            PurchaseOrderComment.objects.create(
                purchase_order=instance,
                user=instance.created_by,  # Use the order creator as default
                comment_type='status_change',
                comment=f"Status geändert von '{old_order.get_status_display()}' zu '{instance.get_status_display()}'",
                old_status=old_order.status,
                new_status=instance.status,
                is_public=True  # Status changes are usually public
            )

            # Add more detailed information for specific status changes
            if instance.status == 'approved' and instance.approved_by:
                PurchaseOrderComment.objects.create(
                    purchase_order=instance,
                    user=instance.approved_by,
                    comment_type='system',
                    comment=f"Bestellung wurde genehmigt von {instance.approved_by.username}",
                    is_public=True
                )

            elif instance.status == 'rejected' and hasattr(instance, 'rejection_reason') and instance.rejection_reason:
                PurchaseOrderComment.objects.create(
                    purchase_order=instance,
                    user=instance.created_by,
                    comment_type='system',
                    comment=f"Bestellung wurde abgelehnt. Grund: {instance.rejection_reason}",
                    is_public=True
                )

    except PurchaseOrder.DoesNotExist:
        # This would be a new order, but we already check for that earlier
        pass


# Add signals for other events too

@receiver(post_save, sender='inventory.StockMovement')
def track_receipts(sender, instance, created, **kwargs):
    """
    Create comments when stock movements are created from order receipts
    """
    if created and instance.reference and 'Wareneingang' in instance.reference:
        # Extract order number from reference (assuming format like "Wareneingang: ORD-20250101-001")
        try:
            order_number = instance.reference.split(': ')[1].split(' ')[0]
            order = PurchaseOrder.objects.get(order_number=order_number)

            PurchaseOrderComment.objects.create(
                purchase_order=order,
                user=instance.created_by,
                comment_type='system',
                comment=f"Wareneingang für {instance.product.name}: {instance.quantity} {instance.product.unit} in Lager '{instance.warehouse.name}'",
                is_public=True
            )
        except (IndexError, PurchaseOrder.DoesNotExist):
            # If we can't parse the reference or find the order, skip creating a comment
            pass