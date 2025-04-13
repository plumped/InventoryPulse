from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from master_data.models.systemsettings_models import WorkflowSettings
from order.models import PurchaseOrder
from .models import SupplierInterface


@receiver(post_save, sender=PurchaseOrder)
def handle_order_status_change(sender, instance, created, **kwargs):
    """
    Signal-Handler, der bei Statusänderungen einer Bestellung 
    automatischen Bestellversand über eine Schnittstelle auslöst.
    """
    # Wenn die Bestellung gerade erst angelegt wurde, nichts tun
    if created:
        return

    # Prüfen, ob die Bestellung gerade in den Status "approved" gewechselt ist
    if instance.status == 'approved' and instance.tracker.has_changed('status') and instance.tracker.previous('status') == 'pending':
        # In einem neuen Thread ausführen, um die Transaktion nicht zu blockieren
        transaction.on_commit(lambda: check_auto_send_order(instance))


def check_auto_send_order(order):
    """
    Prüft, ob eine Bestellung automatisch gesendet werden soll.
    """
    try:
        # Workflow-Einstellungen abrufen
        workflow_settings = WorkflowSettings.objects.first()
        
        # Wenn automatisches Senden aktiviert ist
        if workflow_settings and workflow_settings.send_order_emails:
            # Standard-Schnittstelle des Lieferanten ermitteln
            interface = SupplierInterface.objects.filter(
                supplier=order.supplier,
                is_default=True,
                is_active=True
            ).first()
            
            if interface:
                from .services import send_order_via_interface
                try:
                    # Bestellung senden
                    send_order_via_interface(order.id, interface.id)
                    
                    # Bestellung als gesendet markieren
                    order.status = 'sent'
                    order.save(update_fields=['status'])
                except Exception as e:
                    # Fehler beim Senden protokollieren
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Fehler beim automatischen Senden der Bestellung {order.order_number}: {str(e)}")
    
    except (WorkflowSettings.DoesNotExist, ObjectDoesNotExist, Exception) as e:
        # Fehler beim Abrufen der Einstellungen protokollieren
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Fehler beim Prüfen des automatischen Bestellversands: {str(e)}")