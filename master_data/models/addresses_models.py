from django.db import models, transaction


class CompanyAddressType(models.TextChoices):
    HEADQUARTERS = 'headquarters', 'Hauptsitz'
    WAREHOUSE = 'warehouse', 'Lager'
    SHIPPING = 'shipping', 'Versandadresse'
    RETURN = 'return', 'Rücksendeadresse'
    BILLING = 'billing', 'Rechnungsadresse'
    OTHER = 'other', 'Sonstige'


class CompanyAddress(models.Model):
    name = models.CharField(max_length=100)
    address_type = models.CharField(max_length=20, choices=CompanyAddressType.choices)
    is_default = models.BooleanField(default=False, help_text="Standardadresse für diesen Typ")
    street = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Unternehmensadresse"
        verbose_name_plural = "Unternehmensadressen"
        ordering = ['address_type', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['address_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_company_address_per_type'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_address_type_display()})"

    @property
    def full_address(self):
        parts = [self.street, f"{self.zip_code} {self.city}", self.country]
        return "\n".join(p for p in parts if p)

    def save(self, *args, **kwargs):
        if self.is_default:
            with transaction.atomic():
                CompanyAddress.objects.filter(
                    address_type=self.address_type,
                    is_default=True
                ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
