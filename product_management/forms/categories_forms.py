from django import forms

from product_management.models.categories import Category


class CategoryForm(forms.ModelForm):
    """Form for creating and updating categories."""

    class Meta:
        model = Category
        fields = ['name', 'description']

    def clean_name(self):
        """Ensure category name is unique."""
        name = self.cleaned_data.get('name')
        instance = getattr(self, 'instance', None)

        # Bei Update: Prüfen, ob der Name bereits verwendet wird (außer bei dieser Kategorie)
        if instance and instance.pk:
            qs = Category.objects.filter(name=name).exclude(pk=instance.pk)
        # Bei Create: Prüfen, ob der Name bereits verwendet wird
        else:
            qs = Category.objects.filter(name=name)

        if qs.exists():
            raise forms.ValidationError('Diese Kategorie existiert bereits.')

        return name
