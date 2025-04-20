from django.apps import AppConfig


class AccessmanagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accessmanagement'
    verbose_name = 'Access & Permissions Management'

    def ready(self):
        """
        Import signals and extensions when the app is ready.
        """
        # Set up security signals
        from .security import setup_security_signals
        setup_security_signals()

        # Import models extension to add properties to Group model
        import importlib
        try:
            importlib.import_module('.models_extension', 'accessmanagement')
        except ImportError:
            pass

        # Set up signal to create user profiles automatically
        from django.db.models.signals import post_save
        from django.contrib.auth.models import User
        from django.dispatch import receiver
        from .models import UserProfile

        @receiver(post_save, sender=User)
        def create_user_profile(sender, instance, created, **kwargs):
            """Create a UserProfile for each new User."""
            if created:
                UserProfile.create_for_user(instance)
