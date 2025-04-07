from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SystemSettings
from core.models import UserProfile
import logging
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatisch ein Benutzerprofil erstellen (falls gewünscht in den Systemeinstellungen).
    """
    # Systemoption prüfen
    settings_enabled = True
    settings_instance = SystemSettings.objects.first()
    if settings_instance:
        settings_enabled = settings_instance.auto_create_user_profile

    if not settings_enabled:
        return

    # Profil erstellen, falls nicht vorhanden
    try:
        UserProfile.objects.get_or_create(user=instance)
    except Exception as e:
        logger.warning(f"[UserProfile] Fehler beim Erstellen für '{instance.username}': {e}")
