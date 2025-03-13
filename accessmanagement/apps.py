from django.apps import AppConfig


class AccessmanagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accessmanagement'
    verbose_name = 'Access & Permissions Management'

    def ready(self):
        """
        Import signals when the app is ready.
        """
        # Import signals or perform other initialization
        pass