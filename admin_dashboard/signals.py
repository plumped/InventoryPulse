from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.management import call_command

from .models import SystemSettings


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create or update a user profile when a user is created.
    """
    from core.models import UserProfile

    # Check system settings to see if auto-creating user profiles is enabled
    try:
        system_settings = SystemSettings.objects.first()
        if system_settings and not system_settings.auto_create_user_profile:
            return
    except:
        # If system settings don't exist, assume auto-creation is desired
        pass

    # Create/update user profile
    if created:
        try:
            # Create new profile
            UserProfile.objects.create(user=instance)
        except Exception as e:
            print(f"Error creating user profile for {instance.username}: {e}")
    else:
        try:
            # Ensure profile exists for existing user
            if not hasattr(instance, 'profile'):
                UserProfile.objects.create(user=instance)
        except Exception as e:
            print(f"Error ensuring user profile for {instance.username}: {e}")