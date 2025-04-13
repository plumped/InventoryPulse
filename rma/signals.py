from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from data_operations.models.performance_models import SupplierPerformanceCalculator, SupplierPerformanceMetric, \
    SupplierPerformance
from order.models import PurchaseOrderComment
from .models import RMA, RMAStatus


@receiver(post_save, sender=RMA)
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


@receiver(post_save, sender=RMA)
def update_supplier_performance_after_rma_change(sender, instance, created, **kwargs):
    """
    Aktualisiert die Leistungsbewertung des Lieferanten, wenn ein RMA erstellt
    oder auf "resolved" gesetzt wird. Dies beeinflusst die Qualitätsbewertung.
    """
    # Nur weitermachen, wenn RMA erstellt wurde oder Status auf RESOLVED oder CANCELLED geändert wurde
    if created or instance.status in [RMAStatus.RESOLVED, RMAStatus.CANCELLED]:
        supplier = instance.supplier

        # Letzten 90 Tage als Zeitraum für Neuberechnung verwenden
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=90)

        # Lieferantenperformance aktualisieren - konzentriere dich auf die Qualitätsmetrik
        try:
            # Nur die Qualitätsmetrik neu berechnen, um Performance zu verbessern
            quality_score, quality_orders = SupplierPerformanceCalculator.calculate_rma_quality(
                supplier, start_date, end_date
            )

            # Wenn ein gültiger Score berechnet wurde, speichere ihn
            if quality_score is not None:

                # Qualitätsmetrik abrufen oder erstellen
                quality_metric, _ = SupplierPerformanceMetric.objects.get_or_create(
                    code='product_quality',
                    defaults={
                        'name': 'Product Quality',
                        'description': 'Product quality based on the rate of RMAs (Return Merchandise Authorizations)',
                        'metric_type': 'quality',
                        'is_system': True
                    }
                )

                # Performance-Eintrag aktualisieren oder erstellen
                perf, created_perf = SupplierPerformance.objects.update_or_create(
                    supplier=supplier,
                    metric=quality_metric,
                    evaluation_date=end_date,
                    defaults={
                        'value': quality_score,
                        'evaluation_period_start': start_date,
                        'evaluation_period_end': end_date,
                        'notes': f'Automatically updated after RMA {instance.rma_number} change'
                    }
                )

                # Referenz-Bestellungen verknüpfen, wenn ein neuer Performance-Eintrag erstellt wurde
                if created_perf and quality_orders:
                    perf.reference_orders.set(quality_orders)

        except Exception as e:
            # Fehler loggen, aber nicht weitergeben
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating supplier performance after RMA change: {e}")