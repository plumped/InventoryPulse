from django.db import models


class Tax(models.Model):
    """Modell für Mehrwertsteuersätze."""
    name = models.CharField(max_length=100, verbose_name="Name")
    code = models.CharField(max_length=20, unique=True, verbose_name="Steuerkürzel")
    rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Steuersatz (%)")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    is_default = models.BooleanField(default=False, verbose_name="Standard-Steuersatz")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        verbose_name = "Mehrwertsteuersatz"
        verbose_name_plural = "Mehrwertsteuersätze"
        ordering = ['rate']

    def __str__(self):
        return f"{self.name} ({self.rate}%)"

    def save(self, *args, **kwargs):
        # Wenn dieser Steuersatz als Standard markiert wird, alle anderen auf nicht-Standard setzen
        if self.is_default:
            Tax.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_default_tax(cls):
        """Gibt den Standard-Steuersatz zurück. Falls keiner existiert, wird der erste aktive Steuersatz zurückgegeben."""
        default_tax = cls.objects.filter(is_default=True, is_active=True).first()
        if not default_tax:
            default_tax = cls.objects.filter(is_active=True).first()
        return default_tax
