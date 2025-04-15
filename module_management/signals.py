import logging

from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Company, CompanyModuleSubscription, UserCompany, SubscriptionLog, Module

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CompanyModuleSubscription)
def log_subscription_changes(sender, instance, created, **kwargs):
    """Protokolliert Änderungen an Abonnements"""
    if created:
        action = 'subscribe'
        details = f"Neues Abonnement für {instance.module.name}"
    else:
        action = 'change_plan'
        details = f"Abonnement für {instance.module.name} aktualisiert"

    SubscriptionLog.objects.create(
        company=instance.company,
        module=instance.module,
        action=action,
        details=details
    )

    logger.info(f"Subscription change: {details} for company {instance.company.name}")


@receiver(post_delete, sender=CompanyModuleSubscription)
def log_subscription_deletion(sender, instance, **kwargs):
    """Protokolliert das Löschen von Abonnements"""
    SubscriptionLog.objects.create(
        company=instance.company,
        module=instance.module,
        action='unsubscribe',
        details=f"Abonnement für {instance.module.name} gelöscht"
    )

    logger.info(f"Subscription deleted for module {instance.module.name} and company {instance.company.name}")


@receiver(post_save, sender=User)
def create_user_company_profile(sender, instance, created, **kwargs):
    """
    Erstellt automatisch ein UserCompany-Profil für neue Benutzer
    wenn sie keinem Unternehmen zugeordnet sind.
    """
    if created and not hasattr(instance, 'company_profile'):
        # Prüfen, ob es bereits ein Unternehmen mit dem Namen des Benutzers gibt
        # Dies ist nur für automatische Testumgebungen sinnvoll
        company_name = f"{instance.username}'s Unternehmen"

        try:
            # Versuchen, ein passendes Unternehmen zu finden
            company = Company.objects.filter(name__iexact=company_name).first()

            # Wenn kein passendes Unternehmen gefunden wurde, ein neues erstellen
            if not company:
                company = Company.objects.create(
                    name=company_name,
                    subscription_active=True,
                    max_users=5,
                    contact_email=instance.email
                )

                # Dem neuen Unternehmen Basis-Module zuweisen (optional)
                basic_modules = Module.objects.filter(code__in=['product_management', 'inventory'])
                for module in basic_modules:
                    CompanyModuleSubscription.objects.create(
                        company=company,
                        module=module,
                        is_active=True,
                        renewal_type='monthly',
                        auto_renew=True
                    )

            # UserCompany-Eintrag erstellen und als Admin markieren
            UserCompany.objects.create(
                user=instance,
                company=company,
                is_admin=True
            )

            logger.info(f"Created company profile for user {instance.username}")

        except Exception as e:
            logger.error(f"Error creating company profile for user {instance.username}: {str(e)}")
