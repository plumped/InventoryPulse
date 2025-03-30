from datetime import timedelta
from django.utils import timezone
from django.db.models.aggregates import Avg, Min, Max
from django.http.response import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count

from accessmanagement.decorators import permission_required

from .models import Supplier, SupplierProduct, SupplierPerformance, SupplierPerformanceMetric, \
    SupplierPerformanceCalculator
from core.models import Product
from .forms import SupplierForm, SupplierProductForm, SupplierPerformanceForm, DateRangeForm, \
    SupplierPerformanceMetricForm


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

    # Aktuelle Bestellungen für diesen Lieferanten abrufen
    from order.models import PurchaseOrder
    supplier_orders = PurchaseOrder.objects.filter(
        supplier=supplier,
        status__in=['draft', 'pending', 'approved', 'sent', 'partially_received']
    ).order_by('-order_date')[:5]  # Neueste 5 Bestellungen

    context = {
        'supplier': supplier,
        'supplier_products': supplier_products,
        'system_currency': system_currency,
        'supplier_orders': supplier_orders,  # Neue Kontext-Variable für Bestellungen
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

# Add this to suppliers/views.py

@login_required
def get_supplier_products(request):
    """AJAX-Endpunkt zum Abrufen aller Produkte eines Lieferanten."""
    supplier_id = request.GET.get('supplier_id')

    if not supplier_id:
        return JsonResponse({
            'success': False,
            'message': 'Lieferanten-ID erforderlich'
        })

    try:
        # Lieferanten-Produkt-Informationen abrufen
        supplier_products = SupplierProduct.objects.filter(
            supplier_id=supplier_id
        ).select_related('product', 'product__tax')

        # Format the response
        products_data = []
        for sp in supplier_products:
            product = sp.product

            # Get tax information
            tax_id = None
            tax_rate = 0
            if product.tax:
                tax_id = product.tax.id
                tax_rate = product.tax.rate

            products_data.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'supplier_sku': sp.supplier_sku or '',
                'price': float(sp.purchase_price),
                'unit': product.unit,
                'tax_id': tax_id,
                'tax_rate': tax_rate
            })

        return JsonResponse({
            'success': True,
            'products': products_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler: {str(e)}'
        })


@login_required
@permission_required('supplier', 'view')
def supplier_performance_overview(request):
    """Overview of all suppliers' performance metrics."""
    # Get all active metrics
    metrics = SupplierPerformanceMetric.objects.filter(is_active=True)

    # Get default date range (last 90 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=90)

    # Process date range form if submitted
    date_range_form = DateRangeForm(request.GET or None)
    if date_range_form.is_valid():
        start_date = date_range_form.cleaned_data['start_date']
        end_date = date_range_form.cleaned_data['end_date']

    # Get all suppliers with their latest performance metrics
    suppliers = Supplier.objects.filter(is_active=True).prefetch_related('performance_records')

    # Get average scores for each metric across all suppliers
    avg_scores = {}
    for metric in metrics:
        avg = SupplierPerformance.objects.filter(
            metric=metric,
            evaluation_date__gte=start_date,
            evaluation_date__lte=end_date
        ).aggregate(Avg('value'))['value__avg'] or 0
        avg_scores[metric.code] = round(avg, 2)

    # Prepare data for each supplier
    suppliers_data = []
    for supplier in suppliers:
        supplier_data = {
            'supplier': supplier,
            'metrics': {},
            'avg_score': 0,
            'total_weight': 0,
        }

        # Get all performance records for this supplier
        for metric in metrics:
            performance = SupplierPerformance.objects.filter(
                supplier=supplier,
                metric=metric,
                evaluation_date__gte=start_date,
                evaluation_date__lte=end_date
            ).order_by('-evaluation_date').first()

            if performance:
                supplier_data['metrics'][metric.code] = {
                    'value': performance.value,
                    'date': performance.evaluation_date,
                    'weight': metric.weight,
                }
                supplier_data['avg_score'] += performance.value * metric.weight
                supplier_data['total_weight'] += metric.weight
            else:
                supplier_data['metrics'][metric.code] = None

        # Calculate weighted average score
        if supplier_data['total_weight'] > 0:
            supplier_data['avg_score'] = round(supplier_data['avg_score'] / supplier_data['total_weight'], 2)
        else:
            supplier_data['avg_score'] = None

        suppliers_data.append(supplier_data)

    # Sort suppliers by average score (highest first)
    suppliers_data.sort(key=lambda x: x['avg_score'] if x['avg_score'] is not None else -1, reverse=True)

    context = {
        'metrics': metrics,
        'suppliers_data': suppliers_data,
        'avg_scores': avg_scores,
        'date_range_form': date_range_form,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, 'suppliers/performance/performance_overview.html', context)


@login_required
@permission_required('supplier', 'view')
def supplier_performance_detail(request, pk):
    """Detailed view of a specific supplier's performance."""
    supplier = get_object_or_404(Supplier, pk=pk)

    # Get default date range (last 90 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=90)

    # Process date range form if submitted
    date_range_form = DateRangeForm(request.GET or None)
    if date_range_form.is_valid():
        start_date = date_range_form.cleaned_data['start_date']
        end_date = date_range_form.cleaned_data['end_date']

    # Get all active metrics
    metrics = SupplierPerformanceMetric.objects.filter(is_active=True)

    # Get performance data for each metric
    metrics_data = []
    for metric in metrics:
        performances = SupplierPerformance.objects.filter(
            supplier=supplier,
            metric=metric,
            evaluation_date__gte=start_date,
            evaluation_date__lte=end_date
        ).order_by('evaluation_date')

        metric_data = {
            'metric': metric,
            'performances': performances,
            'latest': performances.last(),
            'trend_data': [{'date': p.evaluation_date.strftime('%Y-%m-%d'), 'value': float(p.value)} for p in
                           performances],
            'stats': performances.aggregate(
                avg=Avg('value'),
                min=Min('value'),
                max=Max('value'),
                count=Count('id')
            ),
        }

        metrics_data.append(metric_data)

    # Get all order data for this supplier in the selected period
    from order.models import PurchaseOrder
    orders = PurchaseOrder.objects.filter(
        supplier=supplier,
        order_date__gte=start_date,
        order_date__lte=end_date
    ).order_by('-order_date')

    # Calculate composite score (weighted average)
    total_score = 0
    total_weight = 0

    for data in metrics_data:
        if data['latest']:
            total_score += data['latest'].value * data['metric'].weight
            total_weight += data['metric'].weight

    if total_weight > 0:
        composite_score = round(total_score / total_weight, 2)
    else:
        composite_score = None

    context = {
        'supplier': supplier,
        'metrics_data': metrics_data,
        'orders': orders,
        'date_range_form': date_range_form,
        'start_date': start_date,
        'end_date': end_date,
        'composite_score': composite_score,
    }

    return render(request, 'suppliers/performance/performance_detail.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_performance_add(request, supplier_id):
    """Add a new performance evaluation for a supplier."""
    supplier = get_object_or_404(Supplier, pk=supplier_id)

    if request.method == 'POST':
        form = SupplierPerformanceForm(request.POST)
        if form.is_valid():
            performance = form.save(commit=False)
            performance.supplier = supplier
            performance.evaluated_by = request.user
            performance.save()

            # Handle reference orders if provided
            if 'reference_orders' in request.POST:
                order_ids = request.POST.getlist('reference_orders')
                if order_ids:
                    from order.models import PurchaseOrder
                    reference_orders = PurchaseOrder.objects.filter(id__in=order_ids)
                    performance.reference_orders.set(reference_orders)

            messages.success(request, f'Performance evaluation for {supplier.name} was successfully added.')
            return redirect('supplier_performance_detail', pk=supplier.id)
    else:
        form = SupplierPerformanceForm()

    # Get recent orders for this supplier that can be referenced
    from order.models import PurchaseOrder
    recent_orders = PurchaseOrder.objects.filter(
        supplier=supplier,
        status__in=['received', 'partially_received']
    ).order_by('-order_date')[:10]

    context = {
        'form': form,
        'supplier': supplier,
        'recent_orders': recent_orders,
    }

    return render(request, 'suppliers/performance/performance_form.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_performance_edit(request, pk):
    """Edit an existing performance evaluation."""
    performance = get_object_or_404(SupplierPerformance, pk=pk)
    supplier = performance.supplier

    if request.method == 'POST':
        form = SupplierPerformanceForm(request.POST, instance=performance)
        if form.is_valid():
            form.save()

            # Handle reference orders if provided
            if 'reference_orders' in request.POST:
                order_ids = request.POST.getlist('reference_orders')
                from order.models import PurchaseOrder
                reference_orders = PurchaseOrder.objects.filter(id__in=order_ids)
                performance.reference_orders.set(reference_orders)

            messages.success(request, 'Performance evaluation was successfully updated.')
            return redirect('supplier_performance_detail', pk=supplier.id)
    else:
        form = SupplierPerformanceForm(instance=performance)

    # Get recent orders for this supplier that can be referenced
    from order.models import PurchaseOrder
    recent_orders = PurchaseOrder.objects.filter(
        supplier=supplier,
        status__in=['received', 'partially_received']
    ).order_by('-order_date')[:10]

    # Currently referenced orders
    referenced_orders = performance.reference_orders.all()

    context = {
        'form': form,
        'supplier': supplier,
        'performance': performance,
        'recent_orders': recent_orders,
        'referenced_orders': referenced_orders,
    }

    return render(request, 'suppliers/performance/performance_form.html', context)


@login_required
@permission_required('supplier', 'delete')
def supplier_performance_delete(request, pk):
    """Delete a performance evaluation."""
    performance = get_object_or_404(SupplierPerformance, pk=pk)
    supplier = performance.supplier

    if request.method == 'POST':
        performance.delete()
        messages.success(request, 'Performance evaluation was successfully deleted.')
        return redirect('supplier_performance_detail', pk=supplier.id)

    context = {
        'performance': performance,
        'supplier': supplier,
    }

    return render(request, 'suppliers/performance/performance_confirm_delete.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_performance_calculate(request, supplier_id):
    """Calculate performance metrics automatically for a supplier."""
    supplier = get_object_or_404(Supplier, pk=supplier_id)

    # Get date range if provided
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date and end_date:
        try:
            from datetime import datetime
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date format. Please use YYYY-MM-DD.')
            return redirect('supplier_performance_detail', pk=supplier_id)

    # Calculate metrics
    results = SupplierPerformanceCalculator.calculate_all_metrics(
        supplier,
        start_date=start_date,
        end_date=end_date,
        save_results=True
    )

    # Build success message
    success_parts = []
    for metric_code, data in results.items():
        if data['score'] is not None:
            metric_name = metric_code.replace('_', ' ').title()
            success_parts.append(f"{metric_name}: {data['score']}%")

    if success_parts:
        message = "Calculated metrics: " + ", ".join(success_parts)
        messages.success(request, message)
    else:
        messages.warning(request, "No metrics could be calculated. There may not be enough order data.")

    return redirect('supplier_performance_detail', pk=supplier_id)


@login_required
@permission_required('supplier', 'view')
def supplier_performance_metrics_list(request):
    """List and manage performance metric definitions."""
    metrics = SupplierPerformanceMetric.objects.all().order_by('name')

    context = {
        'metrics': metrics,
    }

    return render(request, 'suppliers/performance/performance_metrics_list.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_performance_metric_create(request):
    """Create a new performance metric definition."""
    if request.method == 'POST':
        form = SupplierPerformanceMetricForm(request.POST)
        if form.is_valid():
            metric = form.save(commit=False)
            metric.is_system = False  # Custom metrics are not system metrics
            metric.save()

            messages.success(request, f'Metric "{metric.name}" was successfully created.')
            return redirect('supplier_performance_metrics_list')
    else:
        form = SupplierPerformanceMetricForm()

    context = {
        'form': form,
        'is_new': True,
    }

    return render(request, 'suppliers/performance/performance_metric_form.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_performance_metric_edit(request, pk):
    """Edit an existing performance metric."""
    metric = get_object_or_404(SupplierPerformanceMetric, pk=pk)

    # Don't allow editing the code of system metrics
    if request.method == 'POST':
        form = SupplierPerformanceMetricForm(request.POST, instance=metric)

        # For system metrics, don't update the code
        if metric.is_system:
            form.fields['code'].disabled = True

        if form.is_valid():
            form.save()
            messages.success(request, f'Metric "{metric.name}" was successfully updated.')
            return redirect('supplier_performance_metrics_list')
    else:
        form = SupplierPerformanceMetricForm(instance=metric)

        # For system metrics, disable the code field
        if metric.is_system:
            form.fields['code'].disabled = True

    context = {
        'form': form,
        'metric': metric,
        'is_new': False,
    }

    return render(request, 'suppliers/performance/performance_metric_form.html', context)


@login_required
@permission_required('supplier', 'delete')
def supplier_performance_metric_delete(request, pk):
    """Delete a performance metric."""
    metric = get_object_or_404(SupplierPerformanceMetric, pk=pk)

    # Don't allow deleting system metrics
    if metric.is_system:
        messages.error(request, "System metrics cannot be deleted.")
        return redirect('supplier_performance_metrics_list')

    if request.method == 'POST':
        name = metric.name
        metric.delete()
        messages.success(request, f'Metric "{name}" was successfully deleted.')
        return redirect('supplier_performance_metrics_list')

    # Check if this metric has associated performance entries
    has_entries = SupplierPerformance.objects.filter(metric=metric).exists()

    context = {
        'metric': metric,
        'has_entries': has_entries,
    }

    return render(request, 'suppliers/performance/performance_metric_confirm_delete.html', context)


@login_required
def get_supplier_performance_data(request, supplier_id):
    """AJAX endpoint to get performance data for charts."""
    supplier = get_object_or_404(Supplier, pk=supplier_id)

    # Get date range if provided
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    metric_code = request.GET.get('metric')

    # Default date range (last 90 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=90)

    # Parse date range if provided
    if start_date_str and end_date_str:
        try:
            from datetime import datetime
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid date format. Please use YYYY-MM-DD.'
            })

    # Get metric if provided
    metric = None
    if metric_code:
        try:
            metric = SupplierPerformanceMetric.objects.get(code=metric_code)
        except SupplierPerformanceMetric.DoesNotExist:
            pass

    # Get performance data for each metric
    if metric:
        # Get data for a specific metric
        performances = SupplierPerformance.objects.filter(
            supplier=supplier,
            metric=metric,
            evaluation_date__gte=start_date,
            evaluation_date__lte=end_date
        ).order_by('evaluation_date')

        data = {
            'metric': {
                'id': metric.id,
                'code': metric.code,
                'name': metric.name,
                'target': float(metric.target_value)
            },
            'performances': [
                {
                    'id': p.id,
                    'date': p.evaluation_date.strftime('%Y-%m-%d'),
                    'value': float(p.value),
                    'notes': p.notes
                }
                for p in performances
            ],
            'stats': {
                'avg': float(performances.aggregate(Avg('value'))['value__avg'] or 0),
                'min': float(performances.aggregate(Min('value'))['value__min'] or 0),
                'max': float(performances.aggregate(Max('value'))['value__max'] or 0),
                'count': performances.count()
            }
        }
    else:
        # Get summary data for all metrics
        metrics = SupplierPerformanceMetric.objects.filter(is_active=True)
        data = {
            'metrics': []
        }

        for m in metrics:
            performances = SupplierPerformance.objects.filter(
                supplier=supplier,
                metric=m,
                evaluation_date__gte=start_date,
                evaluation_date__lte=end_date
            ).order_by('evaluation_date')

            if performances.exists():
                metric_data = {
                    'id': m.id,
                    'code': m.code,
                    'name': m.name,
                    'target': float(m.target_value),
                    'latest': {
                        'id': performances.last().id,
                        'date': performances.last().evaluation_date.strftime('%Y-%m-%d'),
                        'value': float(performances.last().value)
                    },
                    'trend': [
                        {
                            'date': p.evaluation_date.strftime('%Y-%m-%d'),
                            'value': float(p.value)
                        }
                        for p in performances
                    ],
                    'stats': {
                        'avg': float(performances.aggregate(Avg('value'))['value__avg'] or 0),
                        'min': float(performances.aggregate(Min('value'))['value__min'] or 0),
                        'max': float(performances.aggregate(Max('value'))['value__max'] or 0),
                        'count': performances.count()
                    }
                }
                data['metrics'].append(metric_data)

    return JsonResponse({
        'success': True,
        'supplier': {
            'id': supplier.id,
            'name': supplier.name
        },
        'period': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        },
        'data': data
    })