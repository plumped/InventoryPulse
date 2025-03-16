from django.http.response import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count

from accessmanagement.decorators import permission_required

from .models import Supplier, SupplierProduct
from core.models import Product
from .forms import SupplierForm, SupplierProductForm


@login_required
@permission_required('supplier', 'view')
def supplier_list(request):
    """List all suppliers with filtering and search."""
    suppliers_list = Supplier.objects.all()

    # Suche
    search_query = request.GET.get('search', '')
    if search_query:
        suppliers_list = suppliers_list.filter(
            Q(name__icontains=search_query) |
            Q(contact_person__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    # Anzahl der Produkte pro Lieferant ermitteln
    suppliers_with_counts = []
    for supplier in suppliers_list:
        product_count = SupplierProduct.objects.filter(supplier=supplier).count()
        suppliers_with_counts.append({
            'supplier': supplier,
            'product_count': product_count
        })

    context = {
        'suppliers': suppliers_with_counts,
        'search_query': search_query,
    }

    return render(request, 'suppliers/supplier_list.html', context)


@login_required
@permission_required('supplier', 'view')
def supplier_detail(request, pk):
    """Show details for a specific supplier."""
    supplier = get_object_or_404(Supplier, pk=pk)

    # Produkte dieses Lieferanten
    supplier_products = SupplierProduct.objects.filter(supplier=supplier).select_related('product')

    # Systemwährung ermitteln
    from core.models import Currency
    system_currency = Currency.get_default_currency()

    # Umgerechnete Preise berechnen
    for sp in supplier_products:
        # Die effektive Währung für dieses Produkt ermitteln
        product_currency = sp.currency if sp.currency else supplier.default_currency

        # Wenn die Währung nicht die Systemwährung ist, den Preis umrechnen
        if product_currency and product_currency != system_currency:
            # Wechselkurs aus dem Produkt- oder Lieferantenwährungsmodell übernehmen
            exchange_rate = product_currency.exchange_rate
            sp.converted_price = sp.purchase_price * exchange_rate
            sp.system_currency = system_currency
        else:
            sp.converted_price = None

    context = {
        'supplier': supplier,
        'supplier_products': supplier_products,
        'system_currency': system_currency,
    }

    return render(request, 'suppliers/supplier_detail.html', context)


@login_required
@permission_required('supplier', 'create')
def supplier_create(request):
    """Create a new supplier."""
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f'Lieferant "{supplier.name}" wurde erfolgreich erstellt.')
            return redirect('supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm()

    context = {
        'form': form,
    }

    return render(request, 'suppliers/supplier_form.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_update(request, pk):
    """Update an existing supplier."""
    supplier = get_object_or_404(Supplier, pk=pk)

    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f'Lieferant "{supplier.name}" wurde erfolgreich aktualisiert.')
            return redirect('supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm(instance=supplier)

    context = {
        'form': form,
        'supplier': supplier,
    }

    return render(request, 'suppliers/supplier_form.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_product_add(request):
    """Add a product to a supplier."""
    # Vorausgewähltes Produkt oder Lieferant (z.B. aus URL-Parametern)
    preselected_product_id = request.GET.get('product', None)
    preselected_supplier_id = request.GET.get('supplier', None)

    # Initialdaten für das Formular vorbereiten
    initial_data = {}
    supplier = None
    product = None

    if preselected_product_id:
        initial_data['product'] = preselected_product_id
        product = get_object_or_404(Product, pk=preselected_product_id)

    if preselected_supplier_id:
        initial_data['supplier'] = preselected_supplier_id
        supplier = get_object_or_404(Supplier, pk=preselected_supplier_id)

    if request.method == 'POST':
        form = SupplierProductForm(request.POST, initial=initial_data)
        if form.is_valid():
            supplier_product = form.save(commit=False)

            # Sicherstellen, dass die Standardwährung des Lieferanten verwendet wird,
            # wenn keine abweichende Währung angegeben ist
            if not supplier_product.currency and supplier_product.supplier.default_currency:
                # Bei Submit wird keine Währung explizit gesetzt - die effective_currency-Methode
                # des Modells wird automatisch die Lieferantenwährung verwenden
                pass

            supplier_product.save()

            # Wenn dieses Produkt als bevorzugt markiert ist, andere Zuordnungen dieses Produkts auf nicht bevorzugt setzen
            if supplier_product.is_preferred:
                SupplierProduct.objects.filter(
                    product=supplier_product.product
                ).exclude(
                    pk=supplier_product.pk
                ).update(is_preferred=False)

            messages.success(
                request,
                f'Produkt wurde erfolgreich dem Lieferanten hinzugefügt.'
            )

            # Zurück zur Produkt- oder Lieferantendetailseite
            if preselected_product_id:
                return redirect('product_detail', pk=preselected_product_id)
            elif preselected_supplier_id:
                return redirect('supplier_detail', pk=preselected_supplier_id)
            else:
                return redirect('supplier_list')
    else:
        form = SupplierProductForm(initial=initial_data)

    context = {
        'form': form,
        'preselected_product_id': preselected_product_id,
        'preselected_supplier_id': preselected_supplier_id,
        'supplier': supplier,
        'product': product,
    }

    return render(request, 'suppliers/supplier_product_form.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_product_update(request, pk):
    """Update a supplier-product relationship."""
    supplier_product = get_object_or_404(SupplierProduct, pk=pk)

    if request.method == 'POST':
        form = SupplierProductForm(request.POST, instance=supplier_product)
        if form.is_valid():
            supplier_product = form.save()

            # Wenn dieses Produkt als bevorzugt markiert ist, andere Zuordnungen dieses Produkts auf nicht bevorzugt setzen
            if supplier_product.is_preferred:
                SupplierProduct.objects.filter(
                    product=supplier_product.product
                ).exclude(
                    pk=supplier_product.pk
                ).update(is_preferred=False)

            messages.success(
                request,
                f'Lieferanteninformationen für Produkt wurden erfolgreich aktualisiert.'
            )

            # Zurück zur Lieferantendetailseite
            return redirect('supplier_detail', pk=supplier_product.supplier.pk)
    else:
        form = SupplierProductForm(instance=supplier_product)

    context = {
        'form': form,
        'supplier_product': supplier_product,
    }

    return render(request, 'suppliers/supplier_product_form.html', context)


@login_required
@permission_required('supplier', 'delete')
def supplier_product_delete(request, pk):
    """Delete a supplier-product relationship."""
    supplier_product = get_object_or_404(SupplierProduct, pk=pk)
    supplier = supplier_product.supplier
    product = supplier_product.product

    if request.method == 'POST':
        supplier_product.delete()
        messages.success(
            request,
            f'Produkt "{product.name}" wurde erfolgreich von Lieferant "{supplier.name}" entfernt.'
        )

        # Zurück zur Lieferantendetailseite
        return redirect('supplier_detail', pk=supplier.pk)

    context = {
        'supplier_product': supplier_product,
    }

    return render(request, 'suppliers/supplier_product_confirm_delete.html', context)


@login_required
def get_supplier_data(request):
    """AJAX-Endpunkt zum Abrufen der Lieferantendaten inkl. Versandkosten und Mindestbestellwert."""
    supplier_id = request.GET.get('supplier_id')

    if not supplier_id:
        return JsonResponse({'success': False, 'message': 'Lieferanten-ID erforderlich'})

    try:
        # Lieferanten-Informationen abrufen
        supplier = Supplier.objects.get(pk=supplier_id)

        # Get the currency information
        currency_data = {}
        if supplier.default_currency:
            currency_data = {
                'currency_symbol': supplier.default_currency.symbol,
                'currency_code': supplier.default_currency.code,
                'exchange_rate': float(supplier.default_currency.exchange_rate)
            }
        else:
            # Fallback to system default currency
            from core.models import Currency
            default_currency = Currency.get_default_currency()
            if default_currency:
                currency_data = {
                    'currency_symbol': default_currency.symbol,
                    'currency_code': default_currency.code,
                    'exchange_rate': float(default_currency.exchange_rate)
                }

        return JsonResponse({
            'success': True,
            'shipping_cost': float(supplier.shipping_cost),
            'minimum_order_value': float(supplier.minimum_order_value),
            'name': supplier.name,
            **currency_data  # Include currency data in the response
        })
    except Supplier.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Lieferant nicht gefunden'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Fehler: {str(e)}'})