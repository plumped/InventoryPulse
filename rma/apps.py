from django.apps import AppConfig

class RmaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rma'

    def ready(self):
        # Import signal handlers
        import rma.signals