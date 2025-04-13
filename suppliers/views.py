from datetime import timedelta, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q, Count
from django.db.models.aggregates import Avg, Min, Max
from django.http.response import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.timezone import make_aware

from master_data.models.currency import Currency
from rma.models import RMA, RMAStatus
from .forms import SupplierForm, SupplierProductForm, SupplierPerformanceForm, DateRangeForm, \
    SupplierPerformanceMetricForm, SupplierContactForm, SupplierAddressForm
from .models import Supplier, SupplierProduct, SupplierPerformance, SupplierPerformanceMetric, \
    SupplierPerformanceCalculator, SupplierContact, SupplierAddress, AddressType, ContactType


@login_required
@permission_required('supplier.view_supplier', raise_exception=True)

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
@permission_required('supplier.view_supplier', raise_exception=True)

def supplier_detail(request, pk):
    """Show details for a specific supplier."""
    supplier = get_object_or_404(Supplier, pk=pk)

    # Produkte dieses Lieferanten
    supplier_products = SupplierProduct.objects.filter(supplier=supplier).select_related('product')

    # Systemwährung ermitteln
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

    # Get performance data for this supplier
    supplier_performance = None
    active_metrics = SupplierPerformanceMetric.objects.filter(is_active=True)

    if active_metrics.exists():
        # Get the latest performance data for each metric
        metrics_data = []
        total_weighted_score = 0
        total_weight = 0

        for metric in active_metrics:
            latest_performance = SupplierPerformance.objects.filter(
                supplier=supplier,
                metric=metric
            ).order_by('-evaluation_date').first()

            if latest_performance:
                metrics_data.append({
                    'name': metric.name,
                    'value': latest_performance.value,
                    'date': latest_performance.evaluation_date,
                    'weight': metric.weight
                })

                # Add to weighted score
                total_weighted_score += latest_performance.value * metric.weight
                total_weight += metric.weight

        # If we have at least one metric with data
        if metrics_data and total_weight > 0:
            composite_score = round(total_weighted_score / total_weight, 1)
            supplier_performance = {
                'metrics': metrics_data,
                'composite_score': composite_score
            }

    # Adressen und Kontakte nach Typ gruppieren
    address_types = AddressType.choices
    contact_types = ContactType.choices

    # Vorbereiten der Adressen und Kontakte für das Template
    addresses_by_type = []
    for address_type, type_display in address_types:
        addresses = supplier.addresses.filter(address_type=address_type)
        if addresses.exists():
            addresses_by_type.append({
                'type': address_type,
                'display': type_display,
                'addresses': addresses
            })

    contacts_by_type = []
    for contact_type, type_display in contact_types:
        contacts = supplier.contacts.filter(contact_type=contact_type)
        if contacts.exists():
            contacts_by_type.append({
                'type': contact_type,
                'display': type_display,
                'contacts': contacts
            })
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=90)

    # Aktive RMAs zählen
    active_rmas = RMA.objects.filter(
        supplier=supplier,
        created_at__date__gte=start_date,
        status__in=[RMAStatus.PENDING, RMAStatus.APPROVED, RMAStatus.SENT]
    ).count()

    # RMA-Rate berechnen (Anteil der Bestellungen mit RMAs)
    total_orders = PurchaseOrder.objects.filter(
        supplier=supplier,
        order_date__gte=start_date,
        order_date__lte=end_date
    ).count()

    rma_orders = RMA.objects.filter(
        supplier=supplier,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).exclude(status=RMAStatus.DRAFT).values('related_order').distinct().count()

    rma_rate = 0
    if total_orders > 0:
        rma_rate = (rma_orders / total_orders) * 100

    # Durchschnittliche Bearbeitungszeit berechnen
    resolved_rmas = RMA.objects.filter(
        supplier=supplier,
        status=RMAStatus.RESOLVED,
        submission_date__isnull=False,
        resolution_date__isnull=False
    )

    avg_processing_time = None
    if resolved_rmas.exists():
        processing_times = []
        for rma in resolved_rmas:
            delta = rma.resolution_date - rma.submission_date
            processing_times.append(delta.days)

        if processing_times:
            avg_processing_time = sum(processing_times) / len(processing_times)

    # RMA-Qualitätsscore berechnen
    rma_quality_score, _ = SupplierPerformanceCalculator.calculate_rma_quality(
        supplier, start_date, end_date
    )

    # RMA-Performance-Daten zum Kontext hinzufügen
    if supplier_performance:
        supplier_performance['rma_quality'] = rma_quality_score
        supplier_performance['active_rmas'] = active_rmas
        supplier_performance['rma_rate'] = rma_rate
        supplier_performance['avg_processing_time'] = avg_processing_time

    context = {
        'supplier': supplier,
        'supplier_products': supplier_products,
        'system_currency': system_currency,
        'supplier_orders': supplier_orders,
        'supplier_performance': supplier_performance,
        'address_types': address_types,
        'contact_types': contact_types,
        'addresses_by_type': addresses_by_type,
        'contacts_by_type': contacts_by_type,
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
@permission_required('supplier.view_supplier', raise_exception=True)

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
@permission_required('supplier.view_supplier', raise_exception=True)

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
@permission_required('supplier.view_supplier', raise_exception=True)

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

@login_required
@permission_required('supplier', 'edit')
def supplier_address_create(request, supplier_id):
    """Create a new address for a supplier."""
    supplier = get_object_or_404(Supplier, pk=supplier_id)

    if request.method == 'POST':
        form = SupplierAddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.supplier = supplier

            # Wenn diese Adresse als Standard markiert ist, entferne den Standard bei anderen
            if address.is_default:
                supplier.addresses.filter(
                    address_type=address.address_type,
                    is_default=True
                ).update(is_default=False)

            address.save()
            messages.success(request, f'Adresse für {supplier.name} wurde erfolgreich hinzugefügt.')
            return redirect('supplier_detail', pk=supplier.id)
    else:
        form = SupplierAddressForm(initial={'supplier': supplier})

    context = {
        'form': form,
        'supplier': supplier,
        'is_new': True,
    }

    return render(request, 'suppliers/supplier_address_form.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_address_update(request, pk):
    """Update an existing supplier address."""
    address = get_object_or_404(SupplierAddress, pk=pk)
    supplier = address.supplier

    if request.method == 'POST':
        form = SupplierAddressForm(request.POST, instance=address)
        if form.is_valid():
            # Wenn diese Adresse als Standard markiert ist, entferne den Standard bei anderen
            if form.cleaned_data.get('is_default'):
                supplier.addresses.filter(
                    address_type=form.cleaned_data.get('address_type'),
                    is_default=True
                ).exclude(pk=address.pk).update(is_default=False)

            form.save()
            messages.success(request, f'Adresse wurde erfolgreich aktualisiert.')
            return redirect('supplier_detail', pk=supplier.id)
    else:
        form = SupplierAddressForm(instance=address)

    context = {
        'form': form,
        'supplier': supplier,
        'address': address,
        'is_new': False,
    }

    return render(request, 'suppliers/supplier_address_form.html', context)


@login_required
@permission_required('supplier', 'delete')
def supplier_address_delete(request, pk):
    """Delete a supplier address."""
    address = get_object_or_404(SupplierAddress, pk=pk)
    supplier = address.supplier

    if request.method == 'POST':
        # Wenn dies eine Standardadresse war, versuche eine neue Standardadresse zu setzen
        if address.is_default:
            next_default = supplier.addresses.filter(
                address_type=address.address_type
            ).exclude(pk=address.pk).first()

            if next_default:
                next_default.is_default = True
                next_default.save()

        address.delete()
        messages.success(request, f'Adresse wurde erfolgreich gelöscht.')
        return redirect('supplier_detail', pk=supplier.id)

    context = {
        'address': address,
        'supplier': supplier,
    }

    return render(request, 'suppliers/supplier_address_confirm_delete.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_contact_create(request, supplier_id):
    """Create a new contact for a supplier."""
    supplier = get_object_or_404(Supplier, pk=supplier_id)

    if request.method == 'POST':
        form = SupplierContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.supplier = supplier

            # Wenn dieser Kontakt als Standard markiert ist, entferne den Standard bei anderen
            if contact.is_default:
                supplier.contacts.filter(
                    contact_type=contact.contact_type,
                    is_default=True
                ).update(is_default=False)

            contact.save()
            messages.success(request, f'Kontakt für {supplier.name} wurde erfolgreich hinzugefügt.')
            return redirect('supplier_detail', pk=supplier.id)
    else:
        form = SupplierContactForm(initial={'supplier': supplier})

    context = {
        'form': form,
        'supplier': supplier,
        'is_new': True,
    }

    return render(request, 'suppliers/supplier_contact_form.html', context)


@login_required
@permission_required('supplier', 'edit')
def supplier_contact_update(request, pk):
    """Update an existing supplier contact."""
    contact = get_object_or_404(SupplierContact, pk=pk)
    supplier = contact.supplier

    if request.method == 'POST':
        form = SupplierContactForm(request.POST, instance=contact)
        if form.is_valid():
            # Wenn dieser Kontakt als Standard markiert ist, entferne den Standard bei anderen
            if form.cleaned_data.get('is_default'):
                supplier.contacts.filter(
                    contact_type=form.cleaned_data.get('contact_type'),
                    is_default=True
                ).exclude(pk=contact.pk).update(is_default=False)

            form.save()
            messages.success(request, f'Kontakt wurde erfolgreich aktualisiert.')
            return redirect('supplier_detail', pk=supplier.id)
    else:
        form = SupplierContactForm(instance=contact)

    context = {
        'form': form,
        'supplier': supplier,
        'contact': contact,
        'is_new': False,
    }

    return render(request, 'suppliers/supplier_contact_form.html', context)


@login_required
@permission_required('supplier', 'delete')
def supplier_contact_delete(request, pk):
    """Delete a supplier contact."""
    contact = get_object_or_404(SupplierContact, pk=pk)
    supplier = contact.supplier

    if request.method == 'POST':
        # Wenn dies ein Standardkontakt war, versuche einen neuen Standardkontakt zu setzen
        if contact.is_default:
            next_default = supplier.contacts.filter(
                contact_type=contact.contact_type
            ).exclude(pk=contact.pk).first()

            if next_default:
                next_default.is_default = True
                next_default.save()

        contact.delete()
        messages.success(request, f'Kontakt wurde erfolgreich gelöscht.')
        return redirect('supplier_detail', pk=supplier.id)

    context = {
        'contact': contact,
        'supplier': supplier,
    }

    return render(request, 'suppliers/supplier_contact_confirm_delete.html', context)


# AJAX-Endpunkte für den Zugriff auf Adressen und Kontakte

@login_required
def get_supplier_addresses(request):
    """AJAX endpoint to get addresses for a supplier."""
    supplier_id = request.GET.get('supplier_id')
    address_type = request.GET.get('address_type', None)

    if not supplier_id:
        return JsonResponse({'success': False, 'message': 'Supplier ID is required'})

    try:
        supplier = Supplier.objects.get(pk=supplier_id)

        # Filtere Adressen nach Typ, falls angegeben
        addresses = supplier.addresses.all()
        if address_type:
            addresses = addresses.filter(address_type=address_type)

        # Formatiere Adressen für die JSON-Antwort
        addresses_data = []
        for addr in addresses:
            addresses_data.append({
                'id': addr.id,
                'type': addr.address_type,
                'type_display': addr.get_address_type_display(),
                'is_default': addr.is_default,
                'name': addr.name,
                'street': addr.street,
                'street_number': addr.street_number,
                'postal_code': addr.postal_code,
                'city': addr.city,
                'state': addr.state,
                'country': addr.country,
                'full_address': addr.full_address()
            })

        return JsonResponse({
            'success': True,
            'addresses': addresses_data
        })
    except Supplier.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Supplier not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def get_supplier_contacts(request):
    """AJAX endpoint to get contacts for a supplier."""
    supplier_id = request.GET.get('supplier_id')
    contact_type = request.GET.get('contact_type', None)

    if not supplier_id:
        return JsonResponse({'success': False, 'message': 'Supplier ID is required'})

    try:
        supplier = Supplier.objects.get(pk=supplier_id)

        # Filtere Kontakte nach Typ, falls angegeben
        contacts = supplier.contacts.all()
        if contact_type:
            contacts = contacts.filter(contact_type=contact_type)

        # Formatiere Kontakte für die JSON-Antwort
        contacts_data = []
        for contact in contacts:
            contacts_data.append({
                'id': contact.id,
                'type': contact.contact_type,
                'type_display': contact.get_contact_type_display(),
                'is_default': contact.is_default,
                'title': contact.title,
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'full_name': contact.full_name(),
                'position': contact.position,
                'email': contact.email,
                'phone': contact.phone,
                'mobile': contact.mobile
            })

        return JsonResponse({
            'success': True,
            'contacts': contacts_data
        })
    except Supplier.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Supplier not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def get_supplier_rma_info(request):
    """AJAX endpoint to get RMA-specific information for a supplier."""
    supplier_id = request.GET.get('supplier_id')

    if not supplier_id:
        return JsonResponse({'success': False, 'message': 'Supplier ID is required'})

    try:
        supplier = Supplier.objects.get(pk=supplier_id)

        # RMA-Adresse abrufen
        rma_address = supplier.get_rma_address()
        rma_address_data = None
        if rma_address:
            rma_address_data = {
                'id': rma_address.id,
                'name': rma_address.name,
                'full_address': rma_address.full_address()
            }

        # RMA-Kontakt abrufen
        rma_contact = supplier.get_rma_contact()
        rma_contact_data = None
        if rma_contact:
            rma_contact_data = {
                'id': rma_contact.id,
                'full_name': rma_contact.full_name(),
                'email': rma_contact.email,
                'phone': rma_contact.phone
            }

        return JsonResponse({
            'success': True,
            'supplier_name': supplier.name,
            'rma_address': rma_address_data,
            'rma_contact': rma_contact_data
        })
    except Supplier.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Supplier not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# Füge diese Funktion zu suppliers/views.py hinzu, um RMA-Daten für das Dashboard bereitzustellen

@login_required
def get_supplier_rma_performance(request, supplier_id):
    """AJAX-Endpunkt für RMA-Performance-Daten des Lieferanten."""
    try:
        from django.http import JsonResponse
        from django.db.models import Count, Avg, Sum
        from django.utils import timezone
        from datetime import timedelta, datetime
        from suppliers.models import Supplier
        from rma.models import RMA, RMAStatus, RMAIssueType, RMAItem

        supplier = get_object_or_404(Supplier, pk=supplier_id)

        # Datumsbereich aus der Anfrage oder Standard (letzte 12 Monate)
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        try:
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            else:
                start_date = timezone.now().date() - timedelta(days=365)

            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                end_date = timezone.now().date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid date format. Please use YYYY-MM-DD.'
            })

        # RMAs des Lieferanten im Zeitraum abrufen
        rmas = RMA.objects.filter(
            supplier=supplier,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).exclude(status=RMAStatus.DRAFT)

        # Grundlegende Statistiken
        total_rmas = rmas.count()
        resolved_rmas = rmas.filter(status=RMAStatus.RESOLVED).count()
        cancelled_rmas = rmas.filter(status=RMAStatus.CANCELLED).count()
        active_rmas = total_rmas - resolved_rmas - cancelled_rmas

        # Durchschnittliche Bearbeitungszeit berechnen (nur für erledigte RMAs)
        avg_processing_time = None
        resolved_rmas_queryset = rmas.filter(
            status=RMAStatus.RESOLVED,
            submission_date__isnull=False,
            resolution_date__isnull=False
        )

        if resolved_rmas_queryset.exists():
            processing_times = []
            for rma in resolved_rmas_queryset:
                delta = rma.resolution_date - rma.submission_date
                processing_times.append(delta.days)

            if processing_times:
                avg_processing_time = sum(processing_times) / len(processing_times)

        # RMA-Positionen nach Problemtyp
        rma_items = RMAItem.objects.filter(rma__in=rmas)
        issue_types_count = {}

        for issue_type, display in RMAIssueType.choices:
            count = rma_items.filter(issue_type=issue_type).count()
            if count > 0:
                issue_types_count[issue_type] = {
                    'count': count,
                    'display': display
                }

        # Zeitreihen-Daten für monatliche RMAs
        monthly_data = []

        # Start mit dem ersten Tag des Monats von start_date
        current_month = make_aware(datetime.combine(start_date.replace(day=1), time.min))
        end_month = make_aware(datetime.combine(end_date.replace(day=1), time.min))

        while current_month <= end_month:
            # Nächster Monat berechnen
            if current_month.month == 12:
                next_month = make_aware(datetime(current_month.year + 1, 1, 1))
            else:
                next_month = make_aware(datetime(current_month.year, current_month.month + 1, 1))

            # RMAs in diesem Monat zählen
            month_rmas = rmas.filter(
                created_at__gte=current_month,
                created_at__lt=next_month
            )

            monthly_data.append({
                'month': current_month.strftime('%Y-%m'),
                'display': current_month.strftime('%b %Y'),
                'count': month_rmas.count(),
                'resolved': month_rmas.filter(status=RMAStatus.RESOLVED).count(),
                'total_value': float(month_rmas.aggregate(total=Sum('total_value'))['total'] or 0)
            })

            # Zum nächsten Monat weitergehen
            current_month = next_month

        # Berechnung der durchschnittlichen Kosten pro RMA
        total_rma_value = rmas.aggregate(total=Sum('total_value'))['total'] or 0
        avg_rma_value = 0
        if total_rmas > 0:
            avg_rma_value = float(total_rma_value) / total_rmas

        # Die neuesten RMAs für eine Tabelle
        latest_rmas = []
        for rma in rmas.order_by('-created_at')[:10]:
            latest_rmas.append({
                'id': rma.id,
                'rma_number': rma.rma_number,
                'status': rma.get_status_display(),
                'created_at': rma.created_at.strftime('%d.%m.%Y'),
                'total_value': float(rma.total_value),
                'items_count': rma.items.count()
            })

        # Performance-Score basierend auf RMA-Daten
        # Niedrigere Anzahl von RMAs = höherer Score
        from order.models import PurchaseOrder

        # Anzahl der Bestellungen im gleichen Zeitraum
        orders_count = PurchaseOrder.objects.filter(
            supplier=supplier,
            order_date__gte=start_date,
            order_date__lte=end_date
        ).count()

        # Qualitätsscore berechnen
        quality_score = None
        from suppliers.models import SupplierPerformanceCalculator
        score_result, _ = SupplierPerformanceCalculator.calculate_rma_quality(
            supplier, start_date, end_date
        )

        if score_result is not None:
            quality_score = score_result

        # Ergebnisse zurückgeben
        return JsonResponse({
            'success': True,
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            },
            'summary': {
                'total_rmas': total_rmas,
                'active_rmas': active_rmas,
                'resolved_rmas': resolved_rmas,
                'cancelled_rmas': cancelled_rmas,
                'total_value': float(total_rma_value),
                'avg_value': round(avg_rma_value, 2),
                'avg_processing_time': round(avg_processing_time, 1) if avg_processing_time else None,
                'orders_count': orders_count,
                'quality_score': quality_score
            },
            'issue_types': issue_types_count,
            'monthly_data': monthly_data,
            'latest_rmas': latest_rmas,
            'currency': {
                'code': supplier.default_currency.code,
                'symbol': supplier.default_currency.symbol,
            }
        })
    except Exception as e:
        # Log the error for debugging but return a clean JSON response
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_supplier_rma_performance: {str(e)}")

        return JsonResponse({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        })


@login_required
@permission_required('supplier.view_supplier', raise_exception=True)
def supplier_rma_overview(request, pk):
    """Zeigt eine Übersicht aller RMAs für einen bestimmten Lieferanten."""
    supplier = get_object_or_404(Supplier, pk=pk)

    # Zeitraum aus der Anfrage oder Standard (letzte 90 Tage)
    from datetime import timedelta, datetime
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=90)

    date_str_format = '%Y-%m-%d'

    start_date_str = request.GET.get('start_date')
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, date_str_format).date()
        except ValueError:
            pass

    end_date_str = request.GET.get('end_date')
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, date_str_format).date()
        except ValueError:
            pass

    # Formular für Datumsbereich
    initial_dates = {'start_date': start_date, 'end_date': end_date}
    date_range_form = DateRangeForm(initial=initial_dates)

    # RMAs abrufen
    from rma.models import RMA, RMAStatus

    # Filter anwenden
    status_filter = request.GET.get('status')

    rmas = RMA.objects.filter(
        supplier=supplier,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).select_related('created_by')

    if status_filter:
        rmas = rmas.filter(status=status_filter)

    # RMAs nach Status gruppieren
    from django.db.models import Count, Sum

    status_summary = rmas.values('status').annotate(
        count=Count('id'),
        total_value=Sum('total_value')
    ).order_by('status')

    # Für jede Statusgruppe den angezeigten Namen hinzufügen
    for group in status_summary:
        group['display'] = dict(RMAStatus.choices)[group['status']]

    # Gesamtzahl und Wert berechnen
    total_count = sum(group['count'] for group in status_summary)
    total_value = sum(group['total_value'] or 0 for group in status_summary)

    # RMA-Qualitätsscore berechnen
    from suppliers.models import SupplierPerformanceCalculator
    quality_score, _ = SupplierPerformanceCalculator.calculate_rma_quality(
        supplier, start_date, end_date
    )

    context = {
        'supplier': supplier,
        'rmas': rmas.order_by('-created_at'),
        'status_summary': status_summary,
        'total_count': total_count,
        'total_value': total_value,
        'date_range_form': date_range_form,
        'start_date': start_date,
        'end_date': end_date,
        'quality_score': quality_score,
        'selected_status': status_filter
    }

    return render(request, 'suppliers/supplier_rma_overview.html', context)