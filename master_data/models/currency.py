from django.db import models


class Currency(models.Model):
    """Model for currencies used in the system."""
    code = models.CharField(max_length=3, unique=True,
                            help_text="ISO 4217 currency code (e.g., EUR, USD)")
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=5)
    decimal_places = models.IntegerField(default=2)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1.0,
                                        help_text="Exchange rate relative to the default currency")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Währung"
        verbose_name_plural = "Währungen"
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        # If this currency is set as default, set all others to non-default
        if self.is_default:
            Currency.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)

        # If no default currency exists, make this the default
        elif not Currency.objects.filter(is_default=True).exists():
            self.is_default = True

        super().save(*args, **kwargs)

    @classmethod
    def get_default_currency(cls):
        """Returns the default currency. If none is set, returns the first active currency."""
        default_currency = cls.objects.filter(is_default=True, is_active=True).first()
        if not default_currency:
            default_currency = cls.objects.filter(is_active=True).first()
        return default_currency
