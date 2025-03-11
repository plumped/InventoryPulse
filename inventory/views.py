from decimal import Decimal
from random import random

from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Sum, Count, F, Func
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
import csv

from django import forms

from core import models
from core.models import Product, Category, ProductWarehouse
from .models import StockMovement, StockTake, StockTakeItem, Warehouse, Department, WarehouseAccess
from .forms import StockMovementForm, StockTakeForm, StockTakeItemForm, StockTakeFilterForm, DepartmentForm, WarehouseForm
from .services import update_product_stock
from .utils import user_has_warehouse_access
from core.decorators import permission_required
from core.permissions import has_permission


@login_required
@permission_required('inventory', 'view')
def stock_movement_list(request):
    """List all stock movements with filtering and search."""
    # Nur Bewegungen in Lagern, auf die der Benutzer Zugriff hat
    accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                            if user_has_warehouse_access(request.user, w, 'view')]

    movements_list = StockMovement.objects.select_related('product', 'created_by', 'warehouse').filter(
        warehouse__in=accessible_warehouses
    ).order_by('-created_at')

    # Lager-Filter
    warehouse_id = request.GET.get('warehouse', '')
    if warehouse_id:
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
        if user_has_warehouse_access(request.user, warehouse, 'view'):
            movements_list = movements_list.filter(warehouse=warehouse)
        else:
            messages.error(request, "Sie haben keinen Zugriff auf dieses Lager.")

    # Produktfilter
    product_id = request.GET.get('product', '')
    if product_id:
        movements_list = movements_list.filter(product_id=product_id)

    # Bewegungstyp-Filter
    movement_type = request.GET.get('type', '')
    if movement_type:
        movements_list = movements_list.filter(movement_type=movement_type)

    # Referenz- oder Notiz-Suche
    search_query = request.GET.get('search', '')
    if search_query:
        movements_list = movements_list.filter(
            Q(reference__icontains=search_query) |
            Q(notes__icontains=search_query) |
            Q(product__name__icontains=search_query)
        )

    # Datumsbereich-Filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        movements_list = movements_list.filter(created_at__gte=date_from)
    if date_to:
        movements_list = movements_list.filter(created_at__lte=date_to)

    # Paginierung
    paginator = Paginator(movements_list, 25)  # 25 Bewegungen pro Seite
    page = request.GET.get('page')
    try:
        movements = paginator.page(page)
    except PageNotAnInteger:
        movements = paginator.page(1)
    except EmptyPage:
        movements = paginator.page(paginator.num_pages)

    # Alle Produkte für den Filter
    products = Product.objects.all().order_by('name')

    context = {
        'movements': movements,
        'products': products,
        'warehouses': accessible_warehouses,  # Neue Variable
        'warehouse_id': warehouse_id,         # Neue Variable
        'product_id': product_id,
        'movement_type': movement_type,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
    }

    return render(request, 'inventory/stock_movement_list.html', context)

# Ergänzung zu bestehenden Views in inventory/views.py

@login_required
@permission_required('inventory', 'view')
def stock_take_list(request):
    """List all stock takes with filtering."""
    # Nur Inventuren in Lagern anzeigen, auf die der Benutzer Zugriff hat
    accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                             if user_has_warehouse_access(request.user, w, 'view')]

    stock_takes = StockTake.objects.filter(warehouse__in=accessible_warehouses)

    # Lager-Filter
    warehouse_id = request.GET.get('warehouse', '')
    if warehouse_id:
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
        if user_has_warehouse_access(request.user, warehouse, 'view'):
            stock_takes = stock_takes.filter(warehouse=warehouse)

    # Filter Form
    filter_form = StockTakeFilterForm(request.GET or None)
    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        inventory_type = filter_form.cleaned_data.get('inventory_type')  # Neues Feld
        date_from = filter_form.cleaned_data.get('date_from')
        date_to = filter_form.cleaned_data.get('date_to')
        search = filter_form.cleaned_data.get('search')

        if status:
            stock_takes = stock_takes.filter(status=status)
        if inventory_type:  # Neuer Filter
            stock_takes = stock_takes.filter(inventory_type=inventory_type)
        if date_from:
            stock_takes = stock_takes.filter(start_date__gte=date_from)
        if date_to:
            stock_takes = stock_takes.filter(start_date__lte=date_to)
        if search:
            stock_takes = stock_takes.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(notes__icontains=search)
            )

    # Paginierung
    paginator = Paginator(stock_takes, 10)
    page = request.GET.get('page')
    try:
        stock_takes = paginator.page(page)
    except PageNotAnInteger:
        stock_takes = paginator.page(1)
    except EmptyPage:
        stock_takes = paginator.page(paginator.num_pages)

    context = {
        'stock_takes': stock_takes,
        'filter_form': filter_form,
        'warehouses': accessible_warehouses,
        'warehouse_id': warehouse_id,
    }

    return render(request, 'inventory/stock_take_list.html', context)


@login_required
@permission_required('inventory', 'create')
def stock_take_create(request):
    """Create a new stock take."""
    # Lager abrufen, auf die der Benutzer Zugriff hat
    accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                             if user_has_warehouse_access(request.user, w, 'manage_stock')]

    if not accessible_warehouses:
        messages.error(request, "Sie haben keine Berechtigung, Inventuren durchzuführen.")
        return redirect('stock_take_list')

    if request.method == 'POST':
        form = StockTakeForm(request.POST)

        # Stellen Sie sicher, dass nur zugängliche Lager im Formular ausgewählt werden können
        form.fields['warehouse'].queryset = Warehouse.objects.filter(id__in=[w.id for w in accessible_warehouses])

        if form.is_valid():
            stock_take = form.save(commit=False)
            stock_take.created_by = request.user

            # Für rollierende Inventuren das letzte Zyklendatum setzen
            if stock_take.inventory_type == 'rolling' and stock_take.count_frequency > 0:
                stock_take.last_cycle_date = timezone.now().date()

            stock_take.save()

            # Produkte zur Inventur hinzufügen basierend auf dem Inventurtyp
            if stock_take.inventory_type == 'full':
                # Alle Produkte im ausgewählten Lager zur Inventur hinzufügen
                product_warehouses = ProductWarehouse.objects.filter(warehouse=stock_take.warehouse)

                for product_warehouse in product_warehouses:
                    StockTakeItem.objects.create(
                        stock_take=stock_take,
                        product=product_warehouse.product,
                        expected_quantity=product_warehouse.quantity
                    )

            elif stock_take.inventory_type == 'rolling':
                # Nur Produkte der ausgewählten Kategorie hinzufügen
                product_warehouses = ProductWarehouse.objects.filter(warehouse=stock_take.warehouse)

                if stock_take.cycle_count_category:
                    # ABC-Analyse müsste implementiert sein, hier vereinfacht angenommen
                    # In der Realität würden wir hier eine komplexere Abfrage machen
                    if stock_take.cycle_count_category == 'A':
                        # A-Artikel: Höherwertige Produkte (obere 20% nach Wert)
                        product_warehouses = product_warehouses.order_by('-product__purchase_price')[
                                             :int(product_warehouses.count() * 0.2)]
                    elif stock_take.cycle_count_category == 'B':
                        # B-Artikel: Mittlerer Wert (nächste 30%)
                        sorted_pws = product_warehouses.order_by('-product__purchase_price')
                        start_idx = int(product_warehouses.count() * 0.2)
                        end_idx = int(product_warehouses.count() * 0.5)
                        product_warehouses = sorted_pws[start_idx:end_idx]
                    elif stock_take.cycle_count_category == 'C':
                        # C-Artikel: Geringerer Wert (restliche 50%)
                        sorted_pws = product_warehouses.order_by('-product__purchase_price')
                        start_idx = int(product_warehouses.count() * 0.5)
                        product_warehouses = sorted_pws[start_idx:]

                for product_warehouse in product_warehouses:
                    StockTakeItem.objects.create(
                        stock_take=stock_take,
                        product=product_warehouse.product,
                        expected_quantity=product_warehouse.quantity
                    )

            elif stock_take.inventory_type == 'sample':
                # Zufällige Stichprobe von Produkten
                product_warehouses = ProductWarehouse.objects.filter(warehouse=stock_take.warehouse)
                sample_size = min(int(product_warehouses.count() * 0.1), 50)  # 10% oder max 50 Produkte

                # Zufällige Auswahl
                sample_pws = random.sample(list(product_warehouses), sample_size)

                for product_warehouse in sample_pws:
                    StockTakeItem.objects.create(
                        stock_take=stock_take,
                        product=product_warehouse.product,
                        expected_quantity=product_warehouse.quantity
                    )
            else:
                # Typ 'blind' - gleich wie 'full', nur ohne Anzeige der erwarteten Mengen
                product_warehouses = ProductWarehouse.objects.filter(warehouse=stock_take.warehouse)

                for product_warehouse in product_warehouses:
                    StockTakeItem.objects.create(
                        stock_take=stock_take,
                        product=product_warehouse.product,
                        expected_quantity=product_warehouse.quantity
                    )

            messages.success(request,
                             f'Inventur "{stock_take.name}" für Lager "{stock_take.warehouse.name}" wurde erfolgreich erstellt.')
            return redirect('stock_take_detail', pk=stock_take.pk)
    else:
        form = StockTakeForm()
        form.fields['warehouse'].queryset = Warehouse.objects.filter(id__in=[w.id for w in accessible_warehouses])

    context = {
        'form': form,
        'warehouses': accessible_warehouses,
    }

    return render(request, 'inventory/stock_take_form.html', context)


@login_required
@permission_required('inventory', 'view')
def stock_take_detail(request, pk):
    """Show details for a specific stock take."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'view'):
        return HttpResponseForbidden("Sie haben keinen Zugriff auf dieses Lager.")

    # Inventurpositionen mit Filtermöglichkeit
    items = stock_take.stocktakeitem_set.select_related('product')

    # Filter
    category_id = request.GET.get('category', '')
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if category_id:
        items = items.filter(product__category_id=category_id)

    if search_query:
        items = items.filter(
            Q(product__name__icontains=search_query) |
            Q(product__sku__icontains=search_query) |
            Q(product__barcode__icontains=search_query)
        )

    if status_filter == 'counted':
        items = items.filter(is_counted=True)
    elif status_filter == 'not_counted':
        items = items.filter(is_counted=False)
    elif status_filter == 'discrepancy':
        items = items.filter(is_counted=True).exclude(counted_quantity=F('expected_quantity'))

    # Paginierung
    paginator = Paginator(items, 50)  # 50 Produkte pro Seite
    page = request.GET.get('page')
    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        items = paginator.page(1)
    except EmptyPage:
        items = paginator.page(paginator.num_pages)

    # Kategorien für Filter
    categories = Category.objects.all()
    counted_items = stock_take.stocktakeitem_set.filter(is_counted=True).count()

    context = {
        'stock_take': stock_take,
        'items': items,
        'categories': categories,
        'search_query': search_query,
        'category_id': category_id,
        'status_filter': status_filter,
        'counted_items': counted_items,
    }

    return render(request, 'inventory/stock_take_detail.html', context)


@login_required
@permission_required('inventory', 'edit')
def stock_take_update(request, pk):
    """Update an existing stock take."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'manage_stock'):
        return HttpResponseForbidden("Sie haben keine Berechtigung, diese Inventur zu bearbeiten.")

    # Nur Entwürfe können bearbeitet werden
    if stock_take.status != 'draft':
        messages.error(request,
                       f'Inventur kann nicht mehr bearbeitet werden, da sie bereits {stock_take.get_status_display()} ist.')
        return redirect('stock_take_detail', pk=stock_take.pk)

    # Lager abrufen, auf die der Benutzer Zugriff hat
    accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                             if user_has_warehouse_access(request.user, w, 'manage_stock')]

    if request.method == 'POST':
        form = StockTakeForm(request.POST, instance=stock_take)

        # Beschränken Sie die auswählbaren Lager
        form.fields['warehouse'].queryset = Warehouse.objects.filter(id__in=[w.id for w in accessible_warehouses])

        if form.is_valid():
            # Prüfen, ob das Lager geändert wurde
            old_warehouse = stock_take.warehouse
            new_warehouse = form.cleaned_data.get('warehouse')

            stock_take = form.save()

            # Wenn das Lager geändert wurde, Positionen neu erstellen
            if old_warehouse != new_warehouse:
                # Alte Positionen löschen
                stock_take.stocktakeitem_set.all().delete()

                # Neue Positionen für das neue Lager erstellen
                product_warehouses = ProductWarehouse.objects.filter(warehouse=new_warehouse)
                for product_warehouse in product_warehouses:
                    StockTakeItem.objects.create(
                        stock_take=stock_take,
                        product=product_warehouse.product,
                        expected_quantity=product_warehouse.quantity
                    )

            messages.success(request, f'Inventur "{stock_take.name}" wurde erfolgreich aktualisiert.')
            return redirect('stock_take_detail', pk=stock_take.pk)
    else:
        form = StockTakeForm(instance=stock_take)
        form.fields['warehouse'].queryset = Warehouse.objects.filter(id__in=[w.id for w in accessible_warehouses])

    context = {
        'form': form,
        'stock_take': stock_take,
        'warehouses': accessible_warehouses,
    }

    return render(request, 'inventory/stock_take_form.html', context)


@login_required
@permission_required('inventory', 'delete')
def stock_take_delete(request, pk):
    """Delete a stock take."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'manage_stock'):
        return HttpResponseForbidden("Sie haben keine Berechtigung, diese Inventur zu löschen.")

    # Nur Entwürfe können gelöscht werden
    if stock_take.status != 'draft':
        messages.error(request,
                       f'Inventur kann nicht gelöscht werden, da sie bereits {stock_take.get_status_display()} ist.')
        return redirect('stock_take_detail', pk=stock_take.pk)

    if request.method == 'POST':
        stock_take.delete()
        messages.success(request, f'Inventur "{stock_take.name}" wurde erfolgreich gelöscht.')
        return redirect('stock_take_list')

    context = {
        'stock_take': stock_take,
    }

    return render(request, 'inventory/stock_take_confirm_delete.html', context)


@login_required
@permission_required('inventory', 'edit')
def stock_take_start(request, pk):
    """Start a stock take."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'manage_stock'):
        return HttpResponseForbidden("Sie haben keine Berechtigung, diese Inventur zu starten.")

    # Nur Entwürfe können gestartet werden
    if stock_take.status != 'draft':
        messages.error(request,
                       f'Inventur kann nicht gestartet werden, da sie bereits {stock_take.get_status_display()} ist.')
        return redirect('stock_take_detail', pk=stock_take.pk)

    if request.method == 'POST':
        # Aktualisiere den Status
        stock_take.status = 'in_progress'
        stock_take.save()

        messages.success(request,
                         f'Inventur "{stock_take.name}" für Lager "{stock_take.warehouse.name}" wurde gestartet.')
        return redirect('stock_take_detail', pk=stock_take.pk)

    context = {
        'stock_take': stock_take,
    }

    return render(request, 'inventory/stock_take_confirm_start.html', context)


@login_required
@permission_required('inventory', 'edit')
def stock_take_complete(request, pk):
    """Complete a stock take and apply adjustments."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'manage_stock'):
        return HttpResponseForbidden("Sie haben keine Berechtigung, diese Inventur abzuschließen.")

    # Nur laufende Inventuren können abgeschlossen werden
    if stock_take.status != 'in_progress':
        messages.error(request,
                       f'Inventur kann nicht abgeschlossen werden, da sie {stock_take.get_status_display()} ist.')
        return redirect('stock_take_detail', pk=stock_take.pk)

    # Überprüfen, ob alle Positionen gezählt wurden
    uncounted_items = stock_take.stocktakeitem_set.filter(is_counted=False)
    uncounted_count = uncounted_items.count()

    if request.method == 'POST':
        apply_adjustments = request.POST.get('apply_adjustments') == 'yes'
        skip_uncounted = request.POST.get('skip_uncounted') == 'yes'

        if uncounted_count > 0 and not skip_uncounted:
            messages.error(request,
                           f'Es gibt noch {uncounted_count} ungezählte Positionen. Bitte alle Positionen zählen oder "Ungezählte Positionen überspringen" auswählen.')
            return redirect('stock_take_complete', pk=stock_take.pk)

        # Transaktionen für die Bestandsanpassungen
        with transaction.atomic():
            if apply_adjustments:
                # Bestandskorrekturen für alle gezählten Positionen mit Abweichungen
                items_with_discrepancy = stock_take.stocktakeitem_set.filter(is_counted=True).exclude(
                    counted_quantity=F('expected_quantity'))

                for item in items_with_discrepancy:
                    # Bestandskorrektur erstellen
                    StockMovement.objects.create(
                        product=item.product,
                        quantity=item.counted_quantity,
                        movement_type='adj',
                        reference=f'Inventur: {stock_take.name}',
                        notes=f'Bestandskorrektur durch Inventur: Vorher {item.expected_quantity}, Nachher {item.counted_quantity}',
                        created_by=request.user,
                        warehouse=stock_take.warehouse  # Lager hinzufügen
                    )

                    # Produktbestand im Lager aktualisieren
                    try:
                        product_warehouse = ProductWarehouse.objects.get(
                            product=item.product,
                            warehouse=stock_take.warehouse
                        )
                        product_warehouse.quantity = item.counted_quantity
                        product_warehouse.save()
                    except ProductWarehouse.DoesNotExist:
                        # Falls noch kein Eintrag existiert, einen neuen erstellen
                        ProductWarehouse.objects.create(
                            product=item.product,
                            warehouse=stock_take.warehouse,
                            quantity=item.counted_quantity
                        )

            # Inventur abschließen
            stock_take.status = 'completed'
            stock_take.end_date = timezone.now()
            stock_take.completed_by = request.user
            stock_take.save()

        messages.success(request,
                         f'Inventur "{stock_take.name}" für Lager "{stock_take.warehouse.name}" wurde erfolgreich abgeschlossen.')
        if apply_adjustments:
            messages.info(request, f'Bestandskorrekturen wurden angewendet.')

        return redirect('stock_take_detail', pk=stock_take.pk)

    counted_items = stock_take.stocktakeitem_set.filter(is_counted=True).count()
    items_with_discrepancy = stock_take.stocktakeitem_set.filter(
        is_counted=True
    ).exclude(
        counted_quantity=F('expected_quantity')
    )
    discrepancy_count = items_with_discrepancy.count()
    correct_items = counted_items - discrepancy_count

    context = {
        'stock_take': stock_take,
        'uncounted_count': uncounted_count,
        'counted_items': counted_items,
        'items_with_discrepancy': items_with_discrepancy,
        'correct_items': correct_items,
        'discrepancy_count': discrepancy_count,
    }

    return render(request, 'inventory/stock_take_confirm_complete.html', context)


@login_required
@permission_required('inventory', 'edit')
def stock_take_cancel(request, pk):
    """Cancel a stock take."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'manage_stock'):
        return HttpResponseForbidden("Sie haben keine Berechtigung, diese Inventur abzubrechen.")

    # Nur Entwürfe und laufende Inventuren können abgebrochen werden
    if stock_take.status not in ['draft', 'in_progress']:
        messages.error(request,
                       f'Inventur kann nicht abgebrochen werden, da sie bereits {stock_take.get_status_display()} ist.')
        return redirect('stock_take_detail', pk=stock_take.pk)

    if request.method == 'POST':
        stock_take.status = 'cancelled'
        stock_take.end_date = timezone.now()
        stock_take.save()

        messages.success(request,
                         f'Inventur "{stock_take.name}" für Lager "{stock_take.warehouse.name}" wurde abgebrochen.')
        return redirect('stock_take_detail', pk=stock_take.pk)

    context = {
        'stock_take': stock_take,
    }

    return render(request, 'inventory/stock_take_confirm_cancel.html', context)


@login_required
@permission_required('inventory', 'edit')
def stock_take_item_count(request, pk, item_id):
    """Count a specific item in a stock take."""
    stock_take = get_object_or_404(StockTake, pk=pk)
    item = get_object_or_404(StockTakeItem, pk=item_id, stock_take=stock_take)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'manage_stock'):
        return HttpResponseForbidden("Sie haben keine Berechtigung, in dieser Inventur zu zählen.")

    # Nur laufende Inventuren können gezählt werden
    if stock_take.status != 'in_progress':
        messages.error(request,
                       f'Produkte können nicht gezählt werden, da die Inventur {stock_take.get_status_display()} ist.')
        return redirect('stock_take_detail', pk=stock_take.pk)

    if request.method == 'POST':
        form = StockTakeItemForm(request.POST, instance=item)
        if form.is_valid():
            item = form.save(commit=False)
            item.is_counted = True
            item.counted_by = request.user
            item.counted_at = timezone.now()
            item.save()

            # Ajax-Anfrage behandeln
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                response_data = {
                    'success': True,
                    'item_id': item.id,
                    'counted_quantity': item.counted_quantity,
                }

                # Nur bei Nicht-Blindzählungen die Diskrepanz hinzufügen
                if stock_take.display_expected_quantity:
                    response_data.update({
                        'discrepancy': item.get_discrepancy(),
                        'discrepancy_status': item.get_discrepancy_status(),
                    })

                return JsonResponse(response_data)

            messages.success(request, f'Produkt "{item.product.name}" wurde erfolgreich gezählt.')
            next_item_id = request.POST.get('next_item_id')
            if next_item_id:
                return redirect('stock_take_item_count', pk=stock_take.pk, item_id=next_item_id)
            return redirect('stock_take_detail', pk=stock_take.pk)
    else:
        form = StockTakeItemForm(instance=item)

    # Nächstes ungezähltes Produkt suchen
    next_item = StockTakeItem.objects.filter(
        stock_take=stock_take,
        is_counted=False,
        product__name__gt=item.product.name
    ).order_by('product__name').first()

    context = {
        'stock_take': stock_take,
        'item': item,
        'form': form,
        'next_item': next_item,
        'show_expected_quantity': stock_take.display_expected_quantity,
    }

    return render(request, 'inventory/stock_take_item_count.html', context)


@login_required
@permission_required('inventory', 'edit')
def stock_take_count_items(request, pk):
    """Count multiple items in a stock take (optimized counting view)."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'manage_stock'):
        return HttpResponseForbidden("Sie haben keine Berechtigung, in dieser Inventur zu zählen.")

    # Nur laufende Inventuren können gezählt werden
    if stock_take.status != 'in_progress':
        messages.error(request,
                       f'Produkte können nicht gezählt werden, da die Inventur {stock_take.get_status_display()} ist.')
        return redirect('stock_take_detail', pk=stock_take.pk)

    # Filter und Sortierung
    category_id = request.GET.get('category', '')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'name')
    status_filter = request.GET.get('status', 'not_counted')

    items = stock_take.stocktakeitem_set.select_related('product')

    if category_id:
        items = items.filter(product__category_id=category_id)

    if search_query:
        items = items.filter(
            Q(product__name__icontains=search_query) |
            Q(product__sku__icontains=search_query) |
            Q(product__barcode__icontains=search_query)
        )

    if status_filter == 'counted':
        items = items.filter(is_counted=True)
    elif status_filter == 'not_counted':
        items = items.filter(is_counted=False)
    elif status_filter == 'discrepancy':
        items = items.filter(is_counted=True).exclude(counted_quantity=F('expected_quantity'))

    if sort_by == 'name':
        items = items.order_by('product__name')
    elif sort_by == 'sku':
        items = items.order_by('product__sku')
    elif sort_by == 'category':
        items = items.order_by('product__category__name', 'product__name')
    elif sort_by == 'expected':
        items = items.order_by('-expected_quantity')

    # Kategorien für Filter
    categories = Category.objects.all()

    context = {
        'stock_take': stock_take,
        'items': items,
        'categories': categories,
        'search_query': search_query,
        'category_id': category_id,
        'sort_by': sort_by,
        'status_filter': status_filter,
        'warehouse': stock_take.warehouse,  # Lager zur Anzeige hinzufügen
    }

    return render(request, 'inventory/stock_take_count_items.html', context)


@login_required
@permission_required('inventory', 'edit')
def stock_take_barcode_scan(request, pk):
    """Scan barcodes for stock take counting."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'manage_stock'):
        return HttpResponseForbidden("Sie haben keine Berechtigung, in dieser Inventur zu zählen.")

    # Nur laufende Inventuren können gescannt werden
    if stock_take.status != 'in_progress':
        messages.error(request, f'Barcode-Scan nicht möglich, da die Inventur {stock_take.get_status_display()} ist.')
        return redirect('stock_take_detail', pk=stock_take.pk)

    # AJAX-Anfrage für Barcode-Suche
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        barcode = request.POST.get('barcode')

        try:
            product = Product.objects.get(barcode=barcode)
            # Prüfen Sie, ob das Produkt in diesem Lager ist
            try:
                product_warehouse = ProductWarehouse.objects.get(product=product, warehouse=stock_take.warehouse)
                item = StockTakeItem.objects.get(stock_take=stock_take, product=product)

                return JsonResponse({
                    'success': True,
                    'item_id': item.id,
                    'product_name': product.name,
                    'product_sku': product.sku,
                    'expected_quantity': item.expected_quantity,
                    'is_counted': item.is_counted,
                    'counted_quantity': item.counted_quantity,
                    'warehouse_name': stock_take.warehouse.name,
                })
            except (ProductWarehouse.DoesNotExist, StockTakeItem.DoesNotExist):
                return JsonResponse({
                    'success': False,
                    'message': f'Produkt mit Barcode {barcode} ist nicht in diesem Lager vorhanden.'
                })
        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': f'Produkt mit Barcode {barcode} nicht gefunden.'
            })

    context = {
        'stock_take': stock_take,
        'warehouse': stock_take.warehouse,  # Lager zur Anzeige hinzufügen
    }

    return render(request, 'inventory/stock_take_barcode_scan.html', context)


@login_required
@permission_required('inventory', 'view')
def stock_take_report(request, pk):
    """Generate a report for a stock take."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'view'):
        return HttpResponseForbidden("Sie haben keinen Zugriff auf diesen Bericht.")

    # Statistiken berechnen
    total_items = stock_take.stocktakeitem_set.count()
    counted_items = stock_take.stocktakeitem_set.filter(is_counted=True).count()

    # Items mit Abweichungen finden
    items_with_discrepancies = stock_take.stocktakeitem_set.filter(
        is_counted=True
    ).exclude(
        counted_quantity=F('expected_quantity')
    )

    items_with_discrepancy = items_with_discrepancies.count()

    # Prozentsatz der Artikel mit Abweichungen berechnen
    discrepancy_percentage = 0
    if counted_items > 0:
        discrepancy_percentage = (items_with_discrepancy / counted_items) * 100

    # Produkte mit den größten Abweichungen
    top_discrepancies = items_with_discrepancies.annotate(
        discrepancy_abs=Func(F('counted_quantity') - F('expected_quantity'), function='ABS')
    ).order_by('-discrepancy_abs')[:10]

    # Diskrepanz-Prozentsätze für jedes Produkt berechnen
    for item in top_discrepancies:
        discrepancy = item.get_discrepancy()

        # Berechne den Prozentsatz
        if item.expected_quantity != 0:
            item.discrepancy_percentage = (abs(discrepancy) / item.expected_quantity) * 100
        else:
            item.discrepancy_percentage = 0

    # Gesamtwerte
    total_expected = stock_take.stocktakeitem_set.aggregate(Sum('expected_quantity'))['expected_quantity__sum'] or 0
    total_counted = stock_take.stocktakeitem_set.filter(is_counted=True).aggregate(Sum('counted_quantity'))[
                        'counted_quantity__sum'] or 0

    # Differenz und Absolutwert berechnen
    total_difference = total_counted - total_expected
    total_difference_abs = abs(total_difference)

    # Abweichungen nach Kategorie
    categories = []
    for cat in Category.objects.all():
        items = stock_take.stocktakeitem_set.filter(product__category=cat)
        total = items.count()
        items_counted = items.filter(is_counted=True)
        items_with_disc = items_counted.exclude(counted_quantity=F('expected_quantity'))

        discrepancies = items_with_disc.count()
        percentage = 0
        if total > 0:
            percentage = (discrepancies / total) * 100

        categories.append({
            'name': cat.name,
            'total': total,
            'discrepancies': discrepancies,
            'percentage': percentage
        })

    # Produkte ohne Kategorie
    items = stock_take.stocktakeitem_set.filter(product__category=None)
    total = items.count()
    items_counted = items.filter(is_counted=True)
    items_with_disc = items_counted.exclude(counted_quantity=F('expected_quantity'))

    discrepancies = items_with_disc.count()
    percentage = 0
    if total > 0:
        percentage = (discrepancies / total) * 100

    categories.append({
        'name': 'Keine Kategorie',
        'total': total,
        'discrepancies': discrepancies,
        'percentage': percentage
    })

    context = {
        'stock_take': stock_take,
        'warehouse': stock_take.warehouse,  # Lager zur Anzeige hinzufügen
        'total_items': total_items,
        'counted_items': counted_items,
        'items_with_discrepancy': items_with_discrepancy,
        'completion_percentage': stock_take.get_completion_percentage(),
        'discrepancy_percentage': discrepancy_percentage,
        'top_discrepancies': top_discrepancies,
        'total_expected': total_expected,
        'total_counted': total_counted,
        'total_difference': total_difference,
        'total_difference_abs': total_difference_abs,
        'categories': categories,
    }

    return render(request, 'inventory/stock_take_report.html', context)


@login_required
@permission_required('report', 'view')
def stock_take_export_csv(request, pk):
    """Export a stock take to CSV."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, stock_take.warehouse, 'view'):
        return HttpResponseForbidden("Sie haben keinen Zugriff auf diesen Export.")

    # CSV Datei erstellen
    response = HttpResponse(content_type='text/csv')
    response[
        'Content-Disposition'] = f'attachment; filename="inventur_{stock_take.pk}_{stock_take.warehouse.name}_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(
        ['Produkt-ID', 'SKU', 'Produktname', 'Kategorie', 'Lager', 'Erwartet', 'Gezählt', 'Differenz', 'Status',
         'Gezählt von',
         'Gezählt am', 'Anmerkungen'])

    items = stock_take.stocktakeitem_set.select_related('product', 'product__category', 'counted_by').order_by(
        'product__name')

    for item in items:
        writer.writerow([
            item.product.id,
            item.product.sku,
            item.product.name,
            item.product.category.name if item.product.category else '',
            stock_take.warehouse.name,  # Lager hinzufügen
            item.expected_quantity,
            item.counted_quantity if item.is_counted else '',
            item.get_discrepancy() if item.is_counted else '',
            'Gezählt' if item.is_counted else 'Nicht gezählt',
            item.counted_by.username if item.counted_by else '',
            item.counted_at.strftime('%d.%m.%Y %H:%M') if item.counted_at else '',
            item.notes,
        ])

    return response


@login_required
@permission_required('report', 'view')
def stock_take_export_pdf(request, pk):
    """Export a stock take to PDF."""
    stock_take = get_object_or_404(StockTake, pk=pk)

    # Hier würde man eine PDF-Bibliothek wie ReportLab verwenden
    # Für dieses Beispiel geben wir nur eine einfache Nachricht zurück
    messages.info(request,
                  "PDF-Export wurde gestartet. Die Datei wird zum Download angeboten, sobald sie erstellt wurde.")
    return redirect('stock_take_detail', pk=stock_take.pk)


# Beispiel für Lager-Verwaltungs-Views
@login_required
@permission_required('inventory', 'view')
def warehouse_list(request):
    # Nur Lager anzeigen, auf die der Benutzer Zugriff hat
    warehouses = []
    all_warehouses = Warehouse.objects.filter(is_active=True)

    for warehouse in all_warehouses:
        if user_has_warehouse_access(request.user, warehouse, 'view'):
            warehouses.append(warehouse)

    return render(request, 'inventory/warehouse_list.html', {'warehouses': warehouses})


@login_required
@permission_required('inventory', 'view')
def department_management(request):
    # Nur für Administratoren
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur für Administratoren.")

    departments = Department.objects.all()
    return render(request, 'inventory/department_management.html', {'departments': departments})


@login_required
@permission_required('inventory', 'create')
def department_create(request):
    """Neue Abteilung erstellen."""
    # Nur Administratoren können Abteilungen erstellen
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur Administratoren können Abteilungen erstellen.")

    if request.method == 'POST':
        # Hier müsste ein entsprechendes Formular implementiert werden
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            messages.success(request, f'Abteilung "{department.name}" wurde erfolgreich erstellt.')
            return redirect('department_management')
    else:
        form = DepartmentForm()

    context = {
        'form': form,
    }

    return render(request, 'inventory/department_form.html', context)


@login_required
@permission_required('inventory', 'edit')
def department_update(request, pk):
    """Abteilung bearbeiten."""
    department = get_object_or_404(Department, pk=pk)

    # Nur Administratoren können Abteilungen bearbeiten
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur Administratoren können Abteilungen bearbeiten.")

    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            department = form.save()
            messages.success(request, f'Abteilung "{department.name}" wurde erfolgreich aktualisiert.')
            return redirect('department_management')
    else:
        form = DepartmentForm(instance=department)

    context = {
        'department': department,
        'form': form,
    }

    return render(request, 'inventory/department_form.html', context)


@login_required
@permission_required('inventory', 'delete')
def department_delete(request, pk):
    """Abteilung löschen."""
    department = get_object_or_404(Department, pk=pk)

    # Nur Administratoren können Abteilungen löschen
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur Administratoren können Abteilungen löschen.")

    if request.method == 'POST':
        department.delete()
        messages.success(request, f'Abteilung "{department.name}" wurde erfolgreich gelöscht.')
        return redirect('department_management')

    context = {
        'department': department,
    }

    return render(request, 'inventory/department_confirm_delete.html', context)


@login_required
@permission_required('inventory', 'edit')
def department_members(request, pk):
    """Mitglieder einer Abteilung verwalten."""
    department = get_object_or_404(Department, pk=pk)

    # Nur Administratoren oder der Abteilungsleiter können Mitglieder verwalten
    if not (request.user.is_superuser or (department.manager == request.user)):
        return HttpResponseForbidden("Nur Administratoren oder der Abteilungsleiter können Mitglieder verwalten.")

    if request.method == 'POST':
        action = request.GET.get('action')
        member_id = request.GET.get('member_id')

        if action == 'add':
            # Mitglied hinzufügen
            user_id = request.POST.get('user')
            try:
                user = User.objects.get(pk=user_id)
                department.members.add(user)
                messages.success(request, f'Benutzer "{user.username}" wurde erfolgreich zur Abteilung hinzugefügt.')
            except User.DoesNotExist:
                messages.error(request, "Der ausgewählte Benutzer existiert nicht.")
            except Exception as e:
                messages.error(request, f"Fehler beim Hinzufügen des Mitglieds: {str(e)}")

        elif action == 'edit' and member_id:
            # Mitglied bearbeiten
            try:
                user = User.objects.get(pk=member_id)
                role = request.POST.get('role')

                if role == 'manager':
                    department.manager = user
                    department.save()
                    messages.success(request, f'{user.username} wurde zum Abteilungsleiter ernannt.')

                messages.success(request, f'Rolle für {user.username} wurde aktualisiert.')
            except User.DoesNotExist:
                messages.error(request, "Der Benutzer existiert nicht.")

        elif action == 'remove' and member_id:
            # Mitglied entfernen
            try:
                user = User.objects.get(pk=member_id)

                if user == department.manager and not request.user.is_superuser:
                    messages.error(request, "Der Abteilungsleiter kann sich nicht selbst entfernen.")
                else:
                    department.members.remove(user)

                    if user == department.manager:
                        department.manager = None
                        department.save()
                        messages.warning(request,
                                         "Der Abteilungsleiter wurde entfernt. Bitte weisen Sie einen neuen Leiter zu.")

                    messages.success(request, f'Benutzer {user.username} wurde erfolgreich aus der Abteilung entfernt.')
            except User.DoesNotExist:
                messages.error(request, "Der Benutzer existiert nicht.")

    # Alle Benutzer für die Auswahl
    all_users = User.objects.all().order_by('username')

    # Mitglieder der Abteilung abrufen
    members = department.members.all()

    # Verfügbare Benutzer (noch nicht Mitglied)
    available_users = User.objects.exclude(pk__in=members.values_list('pk', flat=True)).order_by('username')

    context = {
        'department': department,
        'members': members,
        'all_users': all_users,
        'available_users': available_users,
    }

    return render(request, 'inventory/department_members.html', context)


@login_required
@permission_required('inventory', 'edit')
def department_add_member(request, pk):
    """Fügt ein Mitglied zur Abteilung hinzu."""
    department = get_object_or_404(Department, pk=pk)

    # Nur Administratoren oder der Abteilungsleiter können Mitglieder hinzufügen
    if not (request.user.is_superuser or (department.manager == request.user)):
        return HttpResponseForbidden("Nur Administratoren oder der Abteilungsleiter können Mitglieder hinzufügen.")

    if request.method == 'POST':
        user_id = request.POST.get('user')

        try:
            user = User.objects.get(pk=user_id)
            # Füge Benutzer zu den Abteilungsmitgliedern hinzu
            department.members.add(user)
            messages.success(request, f'Benutzer "{user.username}" wurde erfolgreich zur Abteilung hinzugefügt.')
        except User.DoesNotExist:
            messages.error(request, "Der ausgewählte Benutzer existiert nicht.")
        except Exception as e:
            messages.error(request, f"Fehler beim Hinzufügen des Mitglieds: {str(e)}")

    return redirect('department_members', pk=department.pk)


@login_required
@permission_required('inventory', 'edit')
def department_edit_member(request, pk, member_id):
    """Bearbeitet die Rolle eines Abteilungsmitglieds."""
    department = get_object_or_404(Department, pk=pk)
    user = get_object_or_404(User, pk=member_id)

    # Nur Administratoren oder der Abteilungsleiter können Mitglieder bearbeiten
    if not (request.user.is_superuser or (department.manager == request.user)):
        return HttpResponseForbidden("Nur Administratoren oder der Abteilungsleiter können Mitglieder bearbeiten.")

    # Prüfen, ob der Benutzer tatsächlich ein Mitglied der Abteilung ist
    if user not in department.members.all():
        messages.error(request, f"Der Benutzer {user.username} ist kein Mitglied der Abteilung.")
        return redirect('department_members', pk=department.pk)

    if request.method == 'POST':
        role = request.POST.get('role')

        # Wenn die neue Rolle "manager" ist, den Benutzer zum Abteilungsleiter machen
        if role == 'manager':
            department.manager = user
            department.save()
            messages.success(request, f'{user.username} wurde zum Abteilungsleiter ernannt.')

        # Wenn die Rolle "admin" ist, könnte eine spezielle Markierung gesetzt werden
        # (Dies erfordert möglicherweise eine Erweiterung Ihres Modells)

        # Bestätigung anzeigen
        messages.success(request, f'Rolle für {user.username} wurde aktualisiert.')

    return redirect('department_members', pk=department.pk)


@login_required
@permission_required('inventory', 'edit')
def department_remove_member(request, pk, member_id):
    """Entfernt ein Mitglied aus der Abteilung."""
    department = get_object_or_404(Department, pk=pk)
    user = get_object_or_404(User, pk=member_id)

    # Nur Administratoren oder der Abteilungsleiter können Mitglieder entfernen
    if not (request.user.is_superuser or (department.manager == request.user)):
        return HttpResponseForbidden("Nur Administratoren oder der Abteilungsleiter können Mitglieder entfernen.")

    # Prüfen, ob der Benutzer tatsächlich ein Mitglied der Abteilung ist
    if user not in department.members.all():
        messages.error(request, f"Der Benutzer {user.username} ist kein Mitglied der Abteilung.")
        return redirect('department_members', pk=department.pk)

    # Verhindern, dass der Abteilungsleiter sich selbst entfernt
    if user == department.manager and not request.user.is_superuser:
        messages.error(request, "Der Abteilungsleiter kann sich nicht selbst entfernen.")
        return redirect('department_members', pk=department.pk)

    if request.method == 'POST':
        # Benutzer aus der Abteilung entfernen
        department.members.remove(user)

        # Wenn der entfernte Benutzer der Abteilungsleiter war, Manager auf null setzen
        if user == department.manager:
            department.manager = None
            department.save()
            messages.warning(request, "Der Abteilungsleiter wurde entfernt. Bitte weisen Sie einen neuen Leiter zu.")

        messages.success(request, f'Benutzer {user.username} wurde erfolgreich aus der Abteilung entfernt.')

    return redirect('department_members', pk=department.pk)

@login_required
@permission_required('inventory', 'admin')
def warehouse_access_management(request):
    """Verwaltung der Lagerzugriffsrechte."""
    # Nur Administratoren können Zugriffe verwalten
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur Administratoren können Lagerzugriffsrechte verwalten.")

    warehouses = Warehouse.objects.filter(is_active=True)
    departments = Department.objects.all()

    if request.method == 'POST':
        # Hier würde man die POST-Daten verarbeiten, um Zugriffsrechte zu aktualisieren
        warehouse_id = request.POST.get('warehouse')
        department_id = request.POST.get('department')

        can_view = request.POST.get('can_view') == 'on'
        can_edit = request.POST.get('can_edit') == 'on'
        can_manage_stock = request.POST.get('can_manage_stock') == 'on'

        if warehouse_id and department_id:
            warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
            department = get_object_or_404(Department, pk=department_id)

            # Zugriffsrecht erstellen oder aktualisieren
            access, created = WarehouseAccess.objects.update_or_create(
                warehouse=warehouse,
                department=department,
                defaults={
                    'can_view': can_view,
                    'can_edit': can_edit,
                    'can_manage_stock': can_manage_stock,
                }
            )

            if created:
                messages.success(request, f'Zugriffsrechte für {department.name} auf {warehouse.name} wurden erstellt.')
            else:
                messages.success(request,
                                 f'Zugriffsrechte für {department.name} auf {warehouse.name} wurden aktualisiert.')

            return redirect('warehouse_access_management')

    # Bestehende Zugriffsrechte abrufen
    access_rights = WarehouseAccess.objects.select_related('warehouse', 'department').all()

    context = {
        'warehouses': warehouses,
        'departments': departments,
        'access_rights': access_rights,
    }

    return render(request, 'inventory/warehouse_access_management.html', context)


@login_required
@permission_required('inventory', 'admin')
def warehouse_access_delete(request, pk):
    """Lagerzugriffsrecht löschen."""
    access = get_object_or_404(WarehouseAccess, pk=pk)

    # Nur Administratoren können Zugriffsrechte löschen
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur Administratoren können Lagerzugriffsrechte löschen.")

    if request.method == 'POST':
        warehouse_name = access.warehouse.name
        department_name = access.department.name
        access.delete()
        messages.success(request, f'Zugriffsrechte für {department_name} auf {warehouse_name} wurden gelöscht.')
        return redirect('warehouse_access_management')

    context = {
        'access': access,
    }

    return render(request, 'inventory/warehouse_access_confirm_delete.html', context)


@login_required
@permission_required('inventory', 'view')
def product_warehouses(request, product_id):
    """Bestandsansicht eines Produkts in allen Lagern."""
    product = get_object_or_404(Product, pk=product_id)

    # Nur Lager anzeigen, auf die der Benutzer Zugriff hat
    accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                             if user_has_warehouse_access(request.user, w, 'view')]

    # Produktbestände in den zugänglichen Lagern abrufen
    product_warehouses = ProductWarehouse.objects.filter(
        product=product,
        warehouse__in=accessible_warehouses
    ).select_related('warehouse')

    # Letzte Bewegungen dieses Produkts
    movements = StockMovement.objects.filter(
        product=product,
        warehouse__in=accessible_warehouses
    ).order_by('-created_at')[:10]

    context = {
        'product': product,
        'product_warehouses': product_warehouses,
        'movements': movements,
    }

    return render(request, 'inventory/product_warehouses.html', context)

@login_required
@permission_required('inventory', 'create')
def warehouse_create(request):
    """Neues Lager erstellen."""
    # Nur Administratoren können Lager erstellen
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur Administratoren können Lager erstellen.")

    if request.method == 'POST':
        form = WarehouseForm(request.POST)
        if form.is_valid():
            warehouse = form.save()
            messages.success(request, f'Lager "{warehouse.name}" wurde erfolgreich erstellt.')
            return redirect('warehouse_detail', pk=warehouse.pk)
    else:
        form = WarehouseForm()

    context = {
        'form': form,
        'title': 'Neues Lager erstellen',
    }

    return render(request, 'inventory/warehouse_form.html', context)


@login_required
@permission_required('inventory', 'view')
def warehouse_detail(request, pk):
    """Detailansicht eines Lagers."""
    warehouse = get_object_or_404(Warehouse, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, warehouse, 'view'):
        return HttpResponseForbidden("Sie haben keinen Zugriff auf dieses Lager.")

    # Produkte im Lager
    products = ProductWarehouse.objects.filter(warehouse=warehouse).select_related('product')

    # Produkte, die NICHT im aktuellen Lager sind
    products_in_warehouse = products.values_list('product_id', flat=True)
    all_products = Product.objects.exclude(id__in=products_in_warehouse).order_by('name')

    # Filterfunktionen
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')

    if search_query:
        products = products.filter(
            Q(product__name__icontains=search_query) |
            Q(product__sku__icontains=search_query) |
            Q(product__barcode__icontains=search_query)
        )

    if category_id:
        products = products.filter(product__category_id=category_id)

    # Letzte Bestandsbewegungen
    recent_movements = StockMovement.objects.filter(
        warehouse=warehouse
    ).order_by('-created_at')[:10]

    # Aktive Inventuren
    active_stock_takes = StockTake.objects.filter(warehouse=warehouse, status='in_progress')

    # Paginierung für Produkte
    paginator = Paginator(products, 25)  # 25 Produkte pro Seite
    page = request.GET.get('page')
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    # Kategorien für Filter
    categories = Category.objects.all()

    context = {
        'warehouse': warehouse,
        'products': products,
        'recent_movements': recent_movements,
        'active_stock_takes': active_stock_takes,
        'can_manage': user_has_warehouse_access(request.user, warehouse, 'manage_stock'),
        'can_edit': user_has_warehouse_access(request.user, warehouse, 'edit'),
        'search_query': search_query,
        'category_id': category_id,
        'categories': categories,
        'all_products': all_products,  # Add this line
    }

    return render(request, 'inventory/warehouse_detail.html', context)


@login_required
@permission_required('inventory', 'edit')
def warehouse_update(request, pk):
    """Lager bearbeiten."""
    warehouse = get_object_or_404(Warehouse, pk=pk)

    # Nur Administratoren können Lager bearbeiten
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur Administratoren können Lager bearbeiten.")

    if request.method == 'POST':
        form = WarehouseForm(request.POST, instance=warehouse)
        if form.is_valid():
            warehouse = form.save()
            messages.success(request, f'Lager "{warehouse.name}" wurde erfolgreich aktualisiert.')
            return redirect('warehouse_detail', pk=warehouse.pk)
    else:
        form = WarehouseForm(instance=warehouse)

    context = {
        'form': form,
        'warehouse': warehouse,
        'title': f'Lager "{warehouse.name}" bearbeiten',
    }

    return render(request, 'inventory/warehouse_form.html', context)


@login_required
@permission_required('inventory', 'delete')
def warehouse_delete(request, pk):
    """Lager löschen."""
    warehouse = get_object_or_404(Warehouse, pk=pk)

    # Nur Administratoren können Lager löschen
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur Administratoren können Lager löschen.")

    # Prüfen, ob Produkte, Bestandsbewegungen oder Inventuren mit diesem Lager verknüpft sind
    product_count = ProductWarehouse.objects.filter(warehouse=warehouse).count()
    movement_count = StockMovement.objects.filter(warehouse=warehouse).count()
    stock_take_count = StockTake.objects.filter(warehouse=warehouse).count()

    if request.method == 'POST':
        if request.POST.get('confirm') == 'yes':
            # Lager deaktivieren statt löschen
            warehouse.is_active = False
            warehouse.save()

            messages.success(request, f'Lager "{warehouse.name}" wurde deaktiviert.')
            return redirect('warehouse_list')

    context = {
        'warehouse': warehouse,
        'product_count': product_count,
        'movement_count': movement_count,
        'stock_take_count': stock_take_count,
    }

    return render(request, 'inventory/warehouse_confirm_delete.html', context)


@login_required
@permission_required('inventory', 'admin')
def warehouse_access_add(request):
    """Neue Lagerzugriffsrechte hinzufügen."""
    # Nur Administratoren können Zugriffsrechte verwalten
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur Administratoren können Lagerzugriffsrechte verwalten.")

    if request.method == 'POST':
        form = WarehouseAccessForm(request.POST)
        if form.is_valid():
            access = form.save()
            messages.success(request,
                             f'Zugriffsrechte für Abteilung "{access.department.name}" auf Lager "{access.warehouse.name}" wurden erstellt.')
            return redirect('warehouse_access_management')
    else:
        form = WarehouseAccessForm()

    context = {
        'form': form,
        'title': 'Neue Lagerzugriffsrechte hinzufügen',
    }

    return render(request, 'inventory/warehouse_access_form.html', context)


@login_required
@permission_required('inventory', 'admin')
def warehouse_access_update(request, pk):
    """Lagerzugriffsrechte bearbeiten."""
    access = get_object_or_404(WarehouseAccess, pk=pk)

    # Nur Administratoren können Zugriffsrechte verwalten
    if not request.user.is_superuser:
        return HttpResponseForbidden("Nur Administratoren können Lagerzugriffsrechte verwalten.")

    if request.method == 'POST':
        form = WarehouseAccessForm(request.POST, instance=access)
        if form.is_valid():
            access = form.save()
            messages.success(request,
                             f'Zugriffsrechte für Abteilung "{access.department.name}" auf Lager "{access.warehouse.name}" wurden aktualisiert.')
            return redirect('warehouse_access_management')
    else:
        form = WarehouseAccessForm(instance=access)

    context = {
        'form': form,
        'access': access,
        'title': f'Zugriffsrechte bearbeiten: {access.department.name} → {access.warehouse.name}',
    }

    return render(request, 'inventory/warehouse_access_form.html', context)


@login_required
@permission_required('inventory', 'edit')
def product_add_to_warehouse(request, warehouse_id):
    """Produkt zu einem Lager hinzufügen."""
    warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

    # Prüfen der Zugriffsrechte
    if not user_has_warehouse_access(request.user, warehouse, 'manage_stock'):
        messages.error(request, "Sie haben keine Berechtigung, Produkte zu diesem Lager hinzuzufügen.")
        return redirect('warehouse_detail', pk=warehouse_id)

    # Produkte, die NICHT im aktuellen Lager sind
    existing_product_ids = ProductWarehouse.objects.filter(warehouse=warehouse).values_list('product_id', flat=True)
    available_products = Product.objects.exclude(id__in=existing_product_ids).order_by('name')

    if request.method == 'POST':
        product_id = request.POST.get('product')
        quantity = request.POST.get('quantity', 0)

        try:
            product = get_object_or_404(Product, pk=product_id)
            quantity = Decimal(quantity)

            # Prüfen, ob das Produkt bereits im Lager existiert
            product_warehouse, created = ProductWarehouse.objects.get_or_create(
                product=product,
                warehouse=warehouse,
                defaults={'quantity': 0}
            )

            # Bestandsbewegung erstellen, wenn eine Anfangsmenge angegeben wurde
            if quantity > 0:
                StockMovement.objects.create(
                    product=product,
                    warehouse=warehouse,
                    quantity=quantity,
                    movement_type='in',
                    reference='Initialbestand',
                    notes=f'Produkt zum Lager {warehouse.name} hinzugefügt',
                    created_by=request.user
                )

                # Bestand aktualisieren
                product_warehouse.quantity = quantity
                product_warehouse.save()

                # Gesamtbestand aktualisieren
                total_stock = ProductWarehouse.objects.filter(product=product).aggregate(
                    total=Sum('quantity'))['total'] or 0
                product.current_stock = total_stock
                product.save()

                messages.success(request,
                                 f'Produkt {product.name} wurde erfolgreich zum Lager {warehouse.name} mit einem Anfangsbestand von {quantity} hinzugefügt.')
            else:
                messages.success(request,
                                 f'Produkt {product.name} wurde erfolgreich zum Lager {warehouse.name} hinzugefügt (Bestand: 0).')

            return redirect('warehouse_detail', pk=warehouse_id)

        except (ValueError, TypeError) as e:
            messages.error(request, f"Fehler beim Hinzufügen des Produkts: {str(e)}")
            return redirect('warehouse_detail', pk=warehouse_id)

    # GET-Anfrage: Formular zum Hinzufügen eines Produkts
    context = {
        'warehouse': warehouse,
        'available_products': available_products,
    }

    return render(request, 'inventory/add_product_to_warehouse.html', context)

@login_required
@permission_required('inventory', 'edit')
def bulk_add_products_to_warehouse(request, warehouse_id):
    """Bulk add products to a warehouse with multiple input methods."""
    warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

    # Zugriffskontrollen
    if not user_has_warehouse_access(request.user, warehouse, 'manage_stock'):
        messages.error(request, "Sie haben keine Berechtigung, Produkte zu diesem Lager hinzuzufügen.")
        return redirect('warehouse_detail', pk=warehouse_id)

    if request.method == 'POST':
        # Verschiedene Eingabemethoden
        input_method = request.POST.get('input_method', 'manual')
        initial_quantity = request.POST.get('initial_quantity', 0)

        try:
            initial_quantity = Decimal(initial_quantity)
        except (ValueError, TypeError):
            initial_quantity = Decimal('0')

        try:
            if input_method == 'manual':
                # Manuelle Eingabe von Produkt-IDs
                product_ids = request.POST.getlist('product_ids')
                products = Product.objects.filter(id__in=product_ids)

            elif input_method == 'sku_range':
                # Bereich von SKUs
                start_sku = request.POST.get('start_sku', '').strip()
                end_sku = request.POST.get('end_sku', '').strip()

                if not (start_sku and end_sku):
                    messages.error(request, "Bitte geben Sie einen Start- und End-SKU an.")
                    return redirect('warehouse_detail', pk=warehouse_id)

                # SKU-Bereich abfragen
                products = Product.objects.filter(
                    sku__gte=start_sku,
                    sku__lte=end_sku
                )

            elif input_method == 'category':
                # Produkte nach Kategorie
                category_id = request.POST.get('category')
                products = Product.objects.filter(category_id=category_id)

            else:
                messages.error(request, "Ungültige Eingabemethode.")
                return redirect('warehouse_detail', pk=warehouse_id)

            # Überprüfen, ob Produkte gefunden wurden
            if not products.exists():
                messages.warning(request, "Keine Produkte gefunden.")
                return redirect('warehouse_detail', pk=warehouse_id)

            # Produkte zum Lager hinzufügen
            added_products = 0
            for product in products:
                # Prüfen, ob Produkt bereits im Lager existiert
                product_warehouse, created = ProductWarehouse.objects.get_or_create(
                    product=product,
                    warehouse=warehouse,
                    defaults={'quantity': 0}
                )

                # Wenn Initialmenge angegeben, Bestandsbewegung erstellen
                if initial_quantity > 0:
                    StockMovement.objects.create(
                        product=product,
                        warehouse=warehouse,
                        quantity=initial_quantity,
                        movement_type='in',
                        reference='Bulk-Import',
                        notes=f'Massenimport in Lager {warehouse.name}',
                        created_by=request.user
                    )

                    # Bestand aktualisieren
                    product_warehouse.quantity = initial_quantity
                    product_warehouse.save()

                    # Gesamtbestand des Produkts aktualisieren
                    total_stock = ProductWarehouse.objects.filter(product=product).aggregate(
                        total=Sum('quantity'))['total'] or 0
                    product.current_stock = total_stock
                    product.save()

                added_products += 1

            # Erfolgsmeldung
            messages.success(request,
                f'{added_products} Produkte wurden erfolgreich zum Lager {warehouse.name} hinzugefügt.'
            )

            return redirect('warehouse_detail', pk=warehouse_id)

        except Exception as e:
            messages.error(request, f"Fehler beim Hinzufügen der Produkte: {str(e)}")
            return redirect('warehouse_detail', pk=warehouse_id)

    # GET-Anfrage: Formular für Bulk-Import vorbereiten
    context = {
        'warehouse': warehouse,
        'categories': Category.objects.all(),
        'all_products': Product.objects.all().order_by('name')
    }

    return render(request, 'inventory/bulk_add_products.html', context)

class WarehouseAccessForm(forms.ModelForm):
    """Form für die Verwaltung von Lagerzugriffsrechten."""

    class Meta:
        model = WarehouseAccess
        fields = ['warehouse', 'department', 'can_view', 'can_edit', 'can_manage_stock']
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'can_view': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_manage_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['warehouse'].queryset = Warehouse.objects.filter(is_active=True).order_by('name')
        self.fields['department'].queryset = Department.objects.all().order_by('name')

        # Prüfen, ob für diese Kombination bereits ein Zugriffsrecht existiert
        if self.instance.pk is None:  # nur bei neuen Einträgen
            self.fields['warehouse'].help_text = "Wählen Sie ein Lager aus."
            self.fields[
                'department'].help_text = "Wählen Sie eine Abteilung aus. Für jede Kombination aus Lager und Abteilung kann es nur einen Zugriffsrecht-Eintrag geben."


@login_required
@permission_required('inventory', 'edit')
def bulk_warehouse_transfer(request):
    """Mehrere Produkte zwischen Lagern verschieben."""

    # Nur Lager anzeigen, auf die der Benutzer Zugriff hat
    managed_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                          if user_has_warehouse_access(request.user, w, 'manage_stock')]

    if not managed_warehouses:
        messages.error(request, "Sie haben keine Berechtigung, Produkte zwischen Lagern zu transferieren.")
        return redirect('warehouse_list')

    if request.method == 'POST':
        source_warehouse_id = request.POST.get('source_warehouse')
        destination_warehouse_id = request.POST.get('destination_warehouse')
        product_ids = request.POST.getlist('product_ids')
        notes = request.POST.get('notes', '')

        if not (source_warehouse_id and destination_warehouse_id and product_ids):
            messages.error(request, "Quelllager, Ziellager und mindestens ein Produkt müssen ausgewählt werden.")
            return redirect('bulk_warehouse_transfer')

        # Verarbeitung der Verschiebung für jedes Produkt
        try:
            source_warehouse = Warehouse.objects.get(pk=source_warehouse_id)
            destination_warehouse = Warehouse.objects.get(pk=destination_warehouse_id)

            # Berechtigungsprüfung
            if not (user_has_warehouse_access(request.user, source_warehouse, 'manage_stock') and
                    user_has_warehouse_access(request.user, destination_warehouse, 'manage_stock')):
                messages.error(request, "Sie haben keine Berechtigung für einen oder beide Lager.")
                return redirect('bulk_warehouse_transfer')

            # Verarbeitung der ausgewählten Produkte
            products_transferred = 0
            errors = []

            for product_id in product_ids:
                try:
                    product = Product.objects.get(pk=product_id)

                    # Bestandsprüfung im Quelllager
                    try:
                        quantity_field_name = f'quantity_{product_id}'
                        transfer_quantity = Decimal(request.POST.get(quantity_field_name, 0))

                        source_product_warehouse = ProductWarehouse.objects.get(
                            product=product, warehouse=source_warehouse)

                        if source_product_warehouse.quantity < transfer_quantity:
                            errors.append(f"Nicht genügend Bestand für {product.name} im Quelllager.")
                            continue

                        # Transfer durchführen
                        with transaction.atomic():
                            # Abgang im Quelllager
                            StockMovement.objects.create(
                                product=product,
                                quantity=transfer_quantity,
                                movement_type='out',
                                reference=f'Bulk-Transfer zu {destination_warehouse.name}',
                                notes=notes,
                                created_by=request.user,
                                warehouse=source_warehouse
                            )

                            # Quelllager-Bestand aktualisieren
                            source_product_warehouse.quantity -= transfer_quantity
                            source_product_warehouse.save()

                            # Zugang im Ziellager
                            StockMovement.objects.create(
                                product=product,
                                quantity=transfer_quantity,
                                movement_type='in',
                                reference=f'Bulk-Transfer von {source_warehouse.name}',
                                notes=notes,
                                created_by=request.user,
                                warehouse=destination_warehouse
                            )

                            # Ziellager-Bestand aktualisieren
                            dest_warehouse_product, created = ProductWarehouse.objects.get_or_create(
                                product=product,
                                warehouse=destination_warehouse,
                                defaults={'quantity': 0}
                            )

                            dest_warehouse_product.quantity += transfer_quantity
                            dest_warehouse_product.save()

                        products_transferred += 1

                    except ProductWarehouse.DoesNotExist:
                        errors.append(f"Kein Bestand von {product.name} im Quelllager vorhanden.")

                except Product.DoesNotExist:
                    errors.append(f"Produkt mit ID {product_id} nicht gefunden.")

            # Meldungen anzeigen
            if products_transferred > 0:
                messages.success(request, f"{products_transferred} Produkte wurden erfolgreich transferiert.")

            if errors:
                for error in errors:
                    messages.warning(request, error)

            return redirect('warehouse_detail', pk=source_warehouse.pk)

        except Exception as e:
            messages.error(request, f"Fehler beim Transfer: {str(e)}")
            return redirect('bulk_warehouse_transfer')

    # Produkte im ersten Lager anzeigen (falls vorhanden)
    products = []
    source_warehouse_id = request.GET.get('source', '')

    if source_warehouse_id:
        try:
            source_warehouse = Warehouse.objects.get(pk=source_warehouse_id)
            if user_has_warehouse_access(request.user, source_warehouse, 'manage_stock'):
                product_warehouses = ProductWarehouse.objects.filter(
                    warehouse=source_warehouse,
                    quantity__gt=0
                ).select_related('product')

                products = [(pw.product, pw.quantity) for pw in product_warehouses]
        except Warehouse.DoesNotExist:
            pass

    context = {
        'managed_warehouses': managed_warehouses,
        'products': products,
        'source_warehouse_id': source_warehouse_id,
    }

    return render(request, 'inventory/bulk_warehouse_transfer.html', context)


@login_required
@permission_required('inventory', 'create')
def stock_take_create_cycle(request, pk):
    """Create a new cycle count based on an existing one."""
    original_stock_take = get_object_or_404(StockTake, pk=pk)

    # Zugriffskontrolle
    if not user_has_warehouse_access(request.user, original_stock_take.warehouse, 'manage_stock'):
        return HttpResponseForbidden("Sie haben keine Berechtigung, für dieses Lager Inventuren zu erstellen.")

    # Nur für rollierende Inventuren
    if original_stock_take.inventory_type != 'rolling':
        messages.error(request, "Nur für rollierende Inventuren können Zykleninventuren erstellt werden.")
        return redirect('stock_take_detail', pk=original_stock_take.pk)

    if request.method == 'POST':
        # Neue Zykleninventur erstellen
        new_stock_take = StockTake.objects.create(
            name=f"{original_stock_take.name} (Zyklus {timezone.now().strftime('%d.%m.%Y')})",
            description=original_stock_take.description,
            warehouse=original_stock_take.warehouse,
            status='draft',
            inventory_type='rolling',
            display_expected_quantity=original_stock_take.display_expected_quantity,
            cycle_count_category=original_stock_take.cycle_count_category,
            count_frequency=original_stock_take.count_frequency,
            last_cycle_date=timezone.now().date(),
            created_by=request.user
        )

        # Produkte entsprechend der Kategorie hinzufügen
        product_warehouses = ProductWarehouse.objects.filter(warehouse=new_stock_take.warehouse)

        if new_stock_take.cycle_count_category:
            # Vereinfachte ABC-Analyse
            if new_stock_take.cycle_count_category == 'A':
                # A-Artikel: Höherwertige Produkte (obere 20% nach Wert)
                product_warehouses = product_warehouses.order_by('-product__purchase_price')[
                                     :int(product_warehouses.count() * 0.2)]
            elif new_stock_take.cycle_count_category == 'B':
                # B-Artikel: Mittlerer Wert (nächste 30%)
                sorted_pws = product_warehouses.order_by('-product__purchase_price')
                start_idx = int(product_warehouses.count() * 0.2)
                end_idx = int(product_warehouses.count() * 0.5)
                product_warehouses = sorted_pws[start_idx:end_idx]
            elif new_stock_take.cycle_count_category == 'C':
                # C-Artikel: Geringerer Wert (restliche 50%)
                sorted_pws = product_warehouses.order_by('-product__purchase_price')
                start_idx = int(product_warehouses.count() * 0.5)
                product_warehouses = sorted_pws[start_idx:]

        for product_warehouse in product_warehouses:
            StockTakeItem.objects.create(
                stock_take=new_stock_take,
                product=product_warehouse.product,
                expected_quantity=product_warehouse.quantity
            )

        # Original aktualisieren
        original_stock_take.last_cycle_date = timezone.now().date()
        original_stock_take.save()

        messages.success(request, f"Neue Zykleninventur '{new_stock_take.name}' wurde erfolgreich erstellt.")
        return redirect('stock_take_detail', pk=new_stock_take.pk)

    context = {
        'stock_take': original_stock_take,
    }

    return render(request, 'inventory/stock_take_create_cycle.html', context)