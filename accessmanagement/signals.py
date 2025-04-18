import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import UserSecuritySettings, PasswordHistory

logger = logging.getLogger('accessmanagement')


@receiver(post_save, sender=User)
def create_user_security_settings(sender, instance, created, **kwargs):
    """
    Create UserSecuritySettings for new users.
    """
    if created:
        UserSecuritySettings.objects.create(user=instance)
        logger.info(f"Created security settings for user {instance.username}")


@receiver(user_logged_in)
def handle_user_login(sender, request, user, **kwargs):
    """
    Reset failed login attempts on successful login.
    """
    try:
        security_settings, created = UserSecuritySettings.objects.get_or_create(
            user=user,
            defaults={
                'password_last_changed': user.last_login or timezone.now(),
            }
        )
        security_settings.reset_failed_login_attempts()
        logger.info(f"User {user.username} logged in successfully")
    except Exception as e:
        logger.error(f"Error handling login for user {user.username}: {str(e)}")


@receiver(user_login_failed)
def handle_login_failed(sender, credentials, request, **kwargs):
    """
    Track failed login attempts.
    """
    try:
        username = credentials.get('username', '')
        if not username:
            return

        user = User.objects.filter(username=username).first()
        if not user:
            return

        security_settings, created = UserSecuritySettings.objects.get_or_create(
            user=user,
            defaults={
                'password_last_changed': user.last_login or timezone.now(),
            }
        )
        security_settings.record_failed_login()
        logger.warning(f"Failed login attempt for user {username}")
    except Exception as e:
        logger.error(f"Error handling failed login for {username}: {str(e)}")


def check_password_history(user, password):
    """
    Check if the password has been used before.
    Returns True if the password is in the history, False otherwise.
    """
    from django.contrib.auth.hashers import check_password

    # Get the password history limit from settings
    history_limit = getattr(settings, 'PASSWORD_HISTORY_COUNT', 5)

    # Get the most recent passwords
    recent_passwords = PasswordHistory.objects.filter(
        user=user
    ).order_by('-created_at')[:history_limit]

    # Check if the new password matches any of the recent passwords
    for history_entry in recent_passwords:
        if check_password(password, history_entry.password):
            return True

    return False


def add_password_to_history(user):
    """
    Add the current password to the history.
    """
    try:
        # Add the current password to history
        PasswordHistory.objects.create(
            user=user,
            password=user.password
        )

        # Update the security settings
        security_settings, created = UserSecuritySettings.objects.get_or_create(
            user=user,
            defaults={
                'password_last_changed': timezone.now(),
            }
        )

        security_settings.password_last_changed = timezone.now()
        security_settings.require_password_change = False
        security_settings.save()

        logger.info(f"Password changed for user {user.username}")
    except Exception as e:
        logger.error(f"Error adding password to history for user {user.username}: {str(e)}")
