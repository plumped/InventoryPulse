from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q

from .models import RMA, RMAStatus
from order.models import PurchaseOrder, PurchaseOrderComment


@receiver(post_save, sender=RMA)
def update_order_status_after_rma_resolution(sender, instance, **kwargs):
    """
    Aktualisiert den Status der zugehörigen Bestellung, wenn alle RMAs erledigt sind.
    Diese Funktion wird ausgeführt, wenn ein RMA gespeichert wird.
    """
    if not instance.related_order:
        return  # Keine zugehörige Bestellung

    # Nur weitermachen, wenn der RMA-Status auf "resolved" oder "cancelled" gesetzt wurde
    if instance.status in [RMAStatus.RESOLVED, RMAStatus.CANCELLED]:
        order = instance.related_order

        # Prüfen, ob noch andere offene RMAs für diese Bestellung existieren
        open_rmas = RMA.objects.filter(
            related_order=order,
            status__in=[
                RMAStatus.DRAFT,
                RMAStatus.PENDING,
                RMAStatus.APPROVED,
                RMAStatus.SENT
            ]
        ).exists()

        # Wenn keine offenen RMAs mehr existieren und die Bestellung den Status "received_with_issues" hat
        if not open_rmas and order.status == 'received_with_issues':
            # Prüfen, ob es noch Bestellpositionen mit Qualitätsproblemen gibt, die nicht in RMAs aufgenommen wurden
            has_other_quality_issues = order.items.filter(
                has_quality_issues=True
            ).exists()

            # Nur aktualisieren, wenn alle Qualitätsprobleme durch RMAs abgedeckt wurden
            if not has_other_quality_issues:
                # Status auf "received" setzen
                old_status = order.status
                order.status = 'received'
                order.save(update_fields=['status'])

                # Kommentar hinzufügen
                PurchaseOrderComment.objects.create(
                    purchase_order=order,
                    user=instance.created_by,  # Verwende den RMA-Ersteller als Fallback
                    comment_type='system',
                    comment=f"Status von 'Erhalten mit Mängeln' auf 'Vollständig erhalten' geändert, da alle RMAs abgeschlossen wurden.",
                    old_status=old_status,
                    new_status=order.status,
                    is_public=True
                )