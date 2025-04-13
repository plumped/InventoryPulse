from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, get_object_or_404, render

from master_data.forms.currency_forms import CurrencyForm
from master_data.models.currency_models import Currency


@login_required
@permission_required('core', 'view')
def currency_list(request):
    """List all currencies."""
    currencies = Currency.objects.all().order_by('code')

    context = {
        'currencies': currencies,
    }

    return render(request, 'core/currency/currency_list.html', context)


@login_required
@permission_required('core', 'create')
def currency_create(request):
    """Create a new currency."""
    if request.method == 'POST':
        form = CurrencyForm(request.POST)
        if form.is_valid():
            currency = form.save()
            messages.success(request, f'Währung "{currency.name}" wurde erfolgreich erstellt.')
            return redirect('currency_list')
    else:
        form = CurrencyForm()

    context = {
        'form': form,
        'title': 'Neue Währung erstellen',
    }

    return render(request, 'core/currency/currency_form.html', context)


@login_required
@permission_required('core', 'edit')
def currency_update(request, pk):
    """Update an existing currency."""
    currency = get_object_or_404(Currency, pk=pk)

    if request.method == 'POST':
        form = CurrencyForm(request.POST, instance=currency)
        if form.is_valid():
            currency = form.save()
            messages.success(request, f'Währung "{currency.name}" wurde erfolgreich aktualisiert.')
            return redirect('currency_list')
    else:
        form = CurrencyForm(instance=currency)

    context = {
        'form': form,
        'currency': currency,
        'title': f'Währung "{currency.name}" bearbeiten',
    }

    return render(request, 'core/currency/currency_form.html', context)


@login_required
@permission_required('core', 'delete')
def currency_delete(request, pk):
    """Delete a currency."""
    currency = get_object_or_404(Currency, pk=pk)

    # Check if this is the default currency
    if currency.is_default:
        messages.error(request, 'Die Standardwährung kann nicht gelöscht werden.')
        return redirect('currency_list')

    # Check if the currency is used in the system
    # This would need to check any foreign key relationships
    # Example: product_count = Product.objects.filter(currency=currency).count()
    # For now, we'll just check if it's in use or not
    is_used = False  # Replace with actual check

    if request.method == 'POST':
        try:
            currency.delete()
            messages.success(request, f'Währung "{currency.name}" wurde erfolgreich gelöscht.')
        except Exception as e:
            messages.error(request, f'Fehler beim Löschen der Währung: {str(e)}')

        return redirect('currency_list')

    context = {
        'currency': currency,
        'is_used': is_used,
    }

    return render(request, 'core/currency/currency_confirm_delete.html', context)
