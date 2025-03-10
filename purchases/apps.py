from django.apps import AppConfig


class PurchasesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'purchases'
    verbose_name = 'Bestellwesen'

    def ready(self):
        import purchases.signals