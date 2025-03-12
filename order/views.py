import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q, Sum, F, Count, Case, When, Value, IntegerField
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from core.decorators import permission_required
from core.models import Product
from suppliers.models import Supplier, SupplierProduct
from inventory.models import Warehouse, StockMovement

from .models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt,
    PurchaseOrderReceiptItem, OrderSuggestion
)
from .forms import PurchaseOrderForm, ReceiveOrderForm
from .services import generate_order_suggestions


@login_required
@permission_required('order', 'view')
def purchase_order_list(request):
    """Liste aller Bestellungen mit Filteroptionen."""
    # Basis-Queryset
    queryset = PurchaseOrder.objects.select_related('supplier', 'created_by').prefetch_related('items')

    # Filter anwenden
    status = request.GET.get('status', '')
    supplier = request.GET.get('supplier', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')

    if status:
        queryset = queryset.filter(status=status)

    if supplier:
        queryset = queryset.filter(supplier_id=supplier)

    if date_from:
        queryset = queryset.filter(order_date__gte=date_from)

    if date_to:
        queryset = queryset.filter(order_date__lte=date_to)

    if search:
        queryset = queryset.filter(
            Q(order_number__icontains=search) |
            Q(supplier__name__icontains=search) |
            Q(notes__icontains=search)
        )

    # Sortierung
    queryset = queryset.order_by('-order_date')

    # Paginierung
    paginator = Paginator(queryset, 20)  # 20 Bestellungen pro Seite
    page = request.GET.get('page')
    try:
        orders = paginator.page(page)
        # Seitenbereich berechnen
        page_range = range(max(1, orders.number - 2), min(paginator.num_pages + 1, orders.number + 3))
    except PageNotAnInteger:
        orders = paginator.page(1)
        page_range = range(1, min(paginator.num_pages + 1, 6))
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)
        page_range = range(max(1, paginator.num_pages - 4), paginator.num_pages + 1)

    # Daten für Filter
    status_choices = PurchaseOrder.STATUS_CHOICES
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')

    context = {
        'orders': orders,
        'page_range': page_range,
        'status_choices': status_choices,
        'suppliers': suppliers,
        'status': status,
        'supplier': supplier,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
    }

    return render(request, 'order/purchase_order_list.html', context)


@login_required
@permission_required('order', 'view')
def purchase_order_detail(request, pk):
    """Detailansicht einer Bestellung."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'created_by', 'approved_by')
        .prefetch_related('items__product', 'receipts'),
        pk=pk
    )

    # Ermitteln, ob Benutzer bestimmte Aktionen durchführen darf
    can_edit = request.user.has_perm('order.edit') and order.status == 'draft'
    can_approve = request.user.has_perm('order.approve') and order.status == 'pending'
    can_receive = request.user.has_perm('order.receive') and order.status in ['sent', 'partially_received']

    # Wareneingangshistorie abrufen
    receipts = order.receipts.select_related('received_by').prefetch_related('items__order_item__product',
                                                                             'items__warehouse')

    context = {
        'order': order,
        'can_edit': can_edit,
        'can_approve': can_approve,
        'can_receive': can_receive,
        'receipts': receipts,
    }

    return render(request, 'order/purchase_order_detail.html', context)


@login_required
@permission_required('order', 'create')
def purchase_order_create(request):
    """Neue Bestellung erstellen."""
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Bestellung erstellen
                order = form.save(commit=False)
                order.created_by = request.user

                # Bestellnummer generieren (Beispiel: ORD-20230501-001)
                today = date.today()
                prefix = f"ORD-{today.strftime('%Y%m%d')}-"

                # Nächste Sequenznummer finden
                last_order = PurchaseOrder.objects.filter(
                    order_number__startswith=prefix
                ).order_by('-order_number').first()

                if last_order:
                    try:
                        last_seq = int(last_order.order_number.split('-')[-1])
                        next_seq = last_seq + 1
                    except ValueError:
                        next_seq = 1
                else:
                    next_seq = 1

                order.order_number = f"{prefix}{next_seq:03d}"
                order.save()

                # Positionen speichern
                process_order_items(request.POST, order)

                # Summen aktualisieren
                order.update_totals()

                messages.success(request, f'Bestellung {order.order_number} wurde erfolgreich erstellt.')
                return redirect('purchase_order_detail', pk=order.pk)
    else:
        form = PurchaseOrderForm()

    # Produktliste für Dropdown
    products = Product.objects.all().order_by('name')

    context = {
        'form': form,
        'products': products,
    }

    return render(request, 'order/purchase_order_form.html', context)


@login_required
@permission_required('order', 'edit')
def purchase_order_update(request, pk):
    """Bestehende Bestellung bearbeiten."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Nur Entwürfe können bearbeitet werden
    if order.status != 'draft':
        messages.error(request,
                       f'Bestellung {order.order_number} kann nicht mehr bearbeitet werden, da sie nicht im Entwurfsstatus ist.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=order)
        if form.is_valid():
            with transaction.atomic():
                # Bestellung speichern
                order = form.save()

                # Positionen aktualisieren
                process_order_items(request.POST, order)

                # Summen aktualisieren
                order.update_totals()

                messages.success(request, f'Bestellung {order.order_number} wurde erfolgreich aktualisiert.')
                return redirect('purchase_order_detail', pk=order.pk)
    else:
        form = PurchaseOrderForm(instance=order)

    # Produktliste für Dropdown
    products = Product.objects.all().order_by('name')

    context = {
        'form': form,
        'products': products,
    }

    return render(request, 'order/purchase_order_form.html', context)


def process_order_items(post_data, order):
    """Verarbeitet die Bestellpositionen aus dem Formular."""
    # Bisherige Positionen abrufen
    existing_items = {item.id: item for item in order.items.all()}
    processed_ids = set()

    # Neue und aktualisierte Positionen verarbeiten
    for key, value in post_data.items():
        # Prüfen, ob es sich um eine Produktauswahl handelt
        if key.startswith('item_product_'):
            # ID des Elements extrahieren (new_X oder Zahl)
            item_id = key.split('item_product_')[1]

            # Produkt ID abrufen
            product_id = value
            if not product_id:
                continue

            # Entsprechende Mengen- und Preisfelder finden
            quantity_key = f'item_quantity_{item_id}'
            price_key = f'item_price_{item_id}'
            supplier_sku_key = f'item_supplier_sku_{item_id}'

            if quantity_key in post_data and price_key in post_data:
                quantity = Decimal(post_data[quantity_key])
                price = Decimal(post_data[price_key])
                supplier_sku = post_data.get(supplier_sku_key, '')

                # Produkt abrufen
                product = get_object_or_404(Product, pk=product_id)

                if item_id.startswith('new_'):
                    # Neue Position erstellen
                    PurchaseOrderItem.objects.create(
                        purchase_order=order,
                        product=product,
                        quantity_ordered=quantity,
                        unit_price=price,
                        supplier_sku=supplier_sku
                    )
                else:
                    # Bestehende Position aktualisieren
                    try:
                        item_id_int = int(item_id)
                        if item_id_int in existing_items:
                            item = existing_items[item_id_int]
                            item.product = product
                            item.quantity_ordered = quantity
                            item.unit_price = price
                            item.supplier_sku = supplier_sku
                            item.save()
                            processed_ids.add(item_id_int)
                    except (ValueError, KeyError):
                        # Fehlerhafte ID überspringen
                        continue

    # Nicht verarbeitete (entfernte) Positionen löschen
    for item_id, item in existing_items.items():
        if item_id not in processed_ids:
            item.delete()

@login_required
@permission_required('order', 'delete')
def purchase_order_delete(request, pk):
    """Bestellung löschen (nur im Entwurfsstatus)."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Nur Entwürfe können gelöscht werden
    if order.status != 'draft':
        messages.error(request,
                       f'Bestellung {order.order_number} kann nicht gelöscht werden, da sie nicht im Entwurfsstatus ist.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        order_number = order.order_number
        order.delete()
        messages.success(request, f'Bestellung {order_number} wurde erfolgreich gelöscht.')
        return redirect('purchase_order_list')

    context = {
        'order': order,
    }

    return render(request, 'order/purchase_order_confirm_delete.html', context)

@login_required
@permission_required('order', 'edit')
def purchase_order_submit(request, pk):
    """Bestellung zur Genehmigung einreichen."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Nur Entwürfe können eingereicht werden
    if order.status != 'draft':
        messages.error(request,
                       f'Bestellung {order.order_number} kann nicht eingereicht werden, da sie nicht im Entwurfsstatus ist.')
        return redirect('purchase_order_detail', pk=order.pk)

    # Prüfen, ob die Bestellung Positionen hat
    if not order.items.exists():
        messages.error(request,
                       f'Bestellung {order.order_number} kann nicht eingereicht werden, da sie keine Positionen enthält.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        order.status = 'pending'
        order.save()

        messages.success(request,
                         f'Bestellung {order.order_number} wurde zur Genehmigung eingereicht.')
        return redirect('purchase_order_detail', pk=order.pk)

    context = {
        'order': order,
    }

    return render(request, 'order/purchase_order_confirm_submit.html', context)

@login_required
@permission_required('order', 'approve')
def purchase_order_approve(request, pk):
    """Bestellung genehmigen."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Nur wartende Bestellungen können genehmigt werden
    if order.status != 'pending':
        messages.error(request,
                       f'Bestellung {order.order_number} kann nicht genehmigt werden, da sie nicht auf Genehmigung wartet.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        order.status = 'approved'
        order.approved_by = request.user
        order.save()

        messages.success(request, f'Bestellung {order.order_number} wurde genehmigt.')
        return redirect('purchase_order_detail', pk=order.pk)

    context = {
        'order': order,
    }

    return render(request, 'order/purchase_order_confirm_approve.html', context)

@login_required
@permission_required('order', 'approve')
def purchase_order_reject(request, pk):
    """Bestellung ablehnen."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Nur wartende Bestellungen können abgelehnt werden
    if order.status != 'pending':
        messages.error(request,
                       f'Bestellung {order.order_number} kann nicht abgelehnt werden, da sie nicht auf Genehmigung wartet.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '')

        # Bestellung zurück auf Entwurf setzen
        order.status = 'draft'
        order.notes += f"\n\nAbgelehnt am {timezone.now().strftime('%d.%m.%Y')} von {request.user.username}.\nGrund: {rejection_reason}"
        order.save()

        messages.success(request,
                         f'Bestellung {order.order_number} wurde abgelehnt und zurück auf Entwurf gesetzt.')
        return redirect('purchase_order_detail', pk=order.pk)

    context = {
        'order': order,
    }

    return render(request, 'order/purchase_order_confirm_reject.html', context)

@login_required
@permission_required('order', 'edit')
def purchase_order_mark_sent(request, pk):
    """Bestellung als bestellt markieren."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Nur genehmigte Bestellungen können als bestellt markiert werden
    if order.status != 'approved':
        messages.error(request,
                       f'Bestellung {order.order_number} kann nicht als bestellt markiert werden, da sie nicht genehmigt ist.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        order.status = 'sent'
        order.save()

        messages.success(request, f'Bestellung {order.order_number} wurde als bestellt markiert.')
        return redirect('purchase_order_detail', pk=order.pk)

    context = {
        'order': order,
    }

    return render(request, 'order/purchase_order_confirm_mark_sent.html', context)

@login_required
@permission_required('order', 'receive')
def purchase_order_receive(request, pk):
    """Wareneingang für eine Bestellung erfassen."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier').prefetch_related('items__product'),
        pk=pk
    )

    # Nur bestellte oder teilweise erhaltene Bestellungen können Wareneingänge haben
    if order.status not in ['sent', 'partially_received']:
        messages.error(request,
                       f'Wareneingang kann nicht erfasst werden, da die Bestellung nicht im Status "Bestellt" oder "Teilweise erhalten" ist.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        form = ReceiveOrderForm(request.POST, order=order)
        if form.is_valid():
            with transaction.atomic():
                # Wareneingang erstellen
                receipt = PurchaseOrderReceipt.objects.create(
                    purchase_order=order,
                    received_by=request.user,
                    notes=form.cleaned_data.get('notes', '')
                )

                # Für jede Position prüfen, ob Menge empfangen wurde
                items_received = False
                all_items_fully_received = True

                for item in order.items.all():
                    quantity_key = f'receive_quantity_{item.id}'
                    warehouse_key = f'warehouse_{item.id}'
                    batch_key = f'batch_{item.id}'
                    expiry_key = f'expiry_{item.id}'

                    if quantity_key in request.POST and warehouse_key in request.POST:
                        quantity = Decimal(request.POST[quantity_key])
                        warehouse_id = request.POST[warehouse_key]
                        batch = request.POST.get(batch_key, '')
                        expiry = request.POST.get(expiry_key, '')

                        if quantity > 0:
                            # Zielwarehouse abrufen
                            warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

                            # Wareneingangposition erstellen
                            receipt_item = PurchaseOrderReceiptItem.objects.create(
                                receipt=receipt,
                                order_item=item,
                                quantity_received=quantity,
                                warehouse=warehouse,
                                batch_number=batch
                            )

                            # Verfallsdatum setzen, falls angegeben
                            if expiry:
                                try:
                                    receipt_item.expiry_date = date.fromisoformat(expiry)
                                    receipt_item.save()
                                except ValueError:
                                    pass  # Ungültiges Datum ignorieren

                            # Bestandsbewegung erstellen
                            StockMovement.objects.create(
                                product=item.product,
                                warehouse=warehouse,
                                quantity=quantity,
                                movement_type='in',
                                reference=f'Wareneingang: {order.order_number}',
                                notes=f'Erhaltene Menge: {quantity}',
                                created_by=request.user
                            )

                            # Produktbestand im Lager aktualisieren oder neu anlegen
                            from core.models import ProductWarehouse
                            product_warehouse, created = ProductWarehouse.objects.get_or_create(
                                product=item.product,
                                warehouse=warehouse,
                                defaults={'quantity': 0}
                            )

                            product_warehouse.quantity += quantity
                            product_warehouse.save()

                            # Bestellposition aktualisieren
                            item.quantity_received += quantity
                            item.save()

                            items_received = True

                            # Prüfen, ob alle Artikel vollständig erhalten wurden
                            if item.quantity_received < item.quantity_ordered:
                                all_items_fully_received = False

                # Bestellstatus aktualisieren, falls Artikel empfangen wurden
                if items_received:
                    if all_items_fully_received:
                        order.status = 'received'
                    else:
                        order.status = 'partially_received'
                    order.save()

                    messages.success(request,
                                     f'Wareneingang für Bestellung {order.order_number} wurde erfolgreich erfasst.')
                else:
                    messages.warning(request, 'Es wurden keine Artikel als empfangen markiert.')

                return redirect('purchase_order_detail', pk=order.pk)
    else:
        form = ReceiveOrderForm(order=order)

    # Verfügbare Lager abrufen
    warehouses = Warehouse.objects.filter(is_active=True)

    context = {
        'order': order,
        'form': form,
        'warehouses': warehouses,
    }

    return render(request, 'order/purchase_order_receive.html', context)

@login_required
@permission_required('order', 'view')
def purchase_order_print(request, pk):
    """Druckansicht einer Bestellung."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'created_by', 'approved_by')
        .prefetch_related('items__product'),
        pk=pk
    )

    context = {
        'order': order,
        'print_mode': True,
    }

    return render(request, 'order/purchase_order_print.html', context)

@login_required
@permission_required('order', 'view')
def purchase_order_export(request, pk):
    """Export einer Bestellung als CSV oder PDF."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    export_format = request.GET.get('format', 'csv')

    if export_format == 'csv':
        # CSV-Export
        response = HttpResponse(content_type='text/csv')
        response[
            'Content-Disposition'] = f'attachment; filename="bestellung_{order.order_number}.csv"'

        import csv
        writer = csv.writer(response)

        # Header
        writer.writerow(
            ['Bestellnummer', 'Lieferant', 'Datum', 'Status', 'Produkt', 'Lieferanten-SKU', 'Menge',
             'Einheit', 'Einzelpreis', 'Gesamtpreis'])

        # Daten
        for item in order.items.all():
            writer.writerow([
                order.order_number,
                order.supplier.name,
                order.order_date.strftime('%d.%m.%Y'),
                order.get_status_display(),
                item.product.name,
                item.supplier_sku,
                item.quantity_ordered,
                item.product.unit,
                item.unit_price,
                item.line_total
            ])

        return response
    else:
        # Andere Formate wie PDF würden hier implementiert
        messages.error(request, f'Das Format "{export_format}" wird nicht unterstützt.')
        return redirect('purchase_order_detail', pk=pk)

@login_required
@permission_required('order', 'view')
def order_suggestions(request):
    """Zeigt Bestellvorschläge basierend auf kritischen Beständen."""
    # Bestellvorschläge abrufen
    suggestions = OrderSuggestion.objects.select_related('product', 'preferred_supplier').order_by(
        'product__name')

    # Nach Lieferant gruppieren
    grouped_suggestions = {}
    for suggestion in suggestions:
        supplier = suggestion.preferred_supplier
        if supplier:
            if supplier not in grouped_suggestions:
                grouped_suggestions[supplier] = []
            grouped_suggestions[supplier].append(suggestion)
        else:
            # Ohne Lieferant
            if None not in grouped_suggestions:
                grouped_suggestions[None] = []
            grouped_suggestions[None].append(suggestion)

    context = {
        'grouped_suggestions': grouped_suggestions,
    }

    return render(request, 'order/order_suggestions.html', context)

@login_required
@permission_required('order', 'edit')
def refresh_order_suggestions(request):
    """Aktualisiert die Bestellvorschläge (AJAX-Endpunkt)."""
    if request.method == 'POST':
        try:
            # Bestellvorschläge neu generieren
            suggestion_count = generate_order_suggestions()

            return JsonResponse({
                'success': True,
                'message': f'{suggestion_count} Bestellvorschläge wurden generiert.',
                'count': suggestion_count
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })

    return JsonResponse({'success': False, 'message': 'Nur POST-Anfragen sind erlaubt.'})


# Korrigiere die create_orders_from_suggestions Funktion in order/views.py

@login_required
@permission_required('order', 'create')
def create_orders_from_suggestions(request):
    """Erstellt Bestellungen basierend auf ausgewählten Bestellvorschlägen."""
    if request.method == 'POST':
        # Ausgewählte Vorschläge ermitteln
        selected_ids = request.POST.getlist('selected_suggestions')

        if not selected_ids:
            messages.warning(request, 'Es wurden keine Bestellvorschläge ausgewählt.')
            return redirect('order_suggestions')

        # Vorschläge nach Lieferant gruppieren
        suggestions_by_supplier = {}
        for suggestion_id in selected_ids:
            try:
                suggestion = OrderSuggestion.objects.select_related('product', 'preferred_supplier').get(
                    pk=suggestion_id)

                # Bestellmenge aus dem Formular abrufen
                quantity_key = f'quantity_{suggestion_id}'
                if quantity_key in request.POST:
                    quantity = Decimal(request.POST[quantity_key])
                else:
                    quantity = suggestion.suggested_order_quantity

                # Nur hinzufügen, wenn Menge > 0
                if quantity <= 0:
                    continue

                supplier = suggestion.preferred_supplier

                # Ohne Lieferant überspringen
                if not supplier:
                    continue

                if supplier not in suggestions_by_supplier:
                    suggestions_by_supplier[supplier] = []

                suggestions_by_supplier[supplier].append({
                    'product': suggestion.product,
                    'quantity': quantity
                })

            except (OrderSuggestion.DoesNotExist, ValueError):
                continue

        # Für jeden Lieferanten eine Bestellung erstellen oder vorhandenen Entwurf aktualisieren
        orders_created = 0
        orders_updated = 0

        for supplier, items in suggestions_by_supplier.items():
            if not items:
                continue

            with transaction.atomic():
                # Prüfen, ob bereits ein Entwurf für diesen Lieferanten existiert
                existing_draft = PurchaseOrder.objects.filter(
                    supplier=supplier,
                    status='draft'
                ).first()

                if existing_draft:
                    # Vorhandenen Entwurf aktualisieren
                    order = existing_draft
                    orders_updated += 1
                else:
                    # Bestellung erstellen
                    # Bestellnummer generieren (z.B. ORD-20230501-001)
                    today = date.today()
                    prefix = f"ORD-{today.strftime('%Y%m%d')}-"

                    # Nächste Sequenznummer finden
                    last_order = PurchaseOrder.objects.filter(
                        order_number__startswith=prefix
                    ).order_by('-order_number').first()

                    if last_order:
                        try:
                            last_seq = int(last_order.order_number.split('-')[-1])
                            next_seq = last_seq + 1
                        except ValueError:
                            next_seq = 1
                    else:
                        next_seq = 1

                    order_number = f"{prefix}{next_seq:03d}"

                    order = PurchaseOrder.objects.create(
                        supplier=supplier,
                        created_by=request.user,
                        status='draft',
                        order_number=order_number
                    )
                    orders_created += 1

                # Positionen hinzufügen oder aktualisieren
                for item in items:
                    # Prüfen, ob das Produkt bereits in der Bestellung ist
                    existing_item = PurchaseOrderItem.objects.filter(
                        purchase_order=order,
                        product=item['product']
                    ).first()

                    # Lieferantenpreis ermitteln
                    unit_price = Decimal('0.00')
                    supplier_sku = ''

                    try:
                        supplier_product = SupplierProduct.objects.get(
                            supplier=supplier,
                            product=item['product']
                        )
                        unit_price = supplier_product.purchase_price
                        supplier_sku = supplier_product.supplier_sku
                    except SupplierProduct.DoesNotExist:
                        pass

                    if existing_item:
                        # Menge erhöhen
                        existing_item.quantity_ordered += item['quantity']
                        existing_item.save()
                    else:
                        # Neue Position erstellen
                        PurchaseOrderItem.objects.create(
                            purchase_order=order,
                            product=item['product'],
                            quantity_ordered=item['quantity'],
                            unit_price=unit_price,
                            supplier_sku=supplier_sku
                        )

                # Summen aktualisieren
                order.update_totals()

        # Erfolgsmeldung anzeigen
        if orders_created > 0 or orders_updated > 0:
            message_parts = []
            if orders_created > 0:
                message_parts.append(f'{orders_created} neue Bestellung(en)')
            if orders_updated > 0:
                message_parts.append(f'{orders_updated} bestehende Bestellung(en) aktualisiert')

            messages.success(request, 'Bestellungen wurden erfolgreich erstellt: ' + ' und '.join(message_parts))
        else:
            messages.warning(request, 'Es konnten keine Bestellungen erstellt werden.')

        # Nach erfolgreichem Erstellen zurück zur Bestellliste
        return redirect('purchase_order_list')

    # GET-Anfragen umleiten
    return redirect('order_suggestions')

@login_required
def get_supplier_product_price(request):
    """AJAX-Endpunkt zum Abrufen des Lieferantenpreises für ein Produkt."""
    product_id = request.GET.get('product_id')
    supplier_id = request.GET.get('supplier_id')

    if not product_id or not supplier_id:
        return JsonResponse(
            {'success': False, 'message': 'Produkt- und Lieferanten-ID erforderlich'})

    try:
        supplier_product = SupplierProduct.objects.get(
            product_id=product_id,
            supplier_id=supplier_id
        )

        return JsonResponse({
            'success': True,
            'price': float(supplier_product.purchase_price),
            'supplier_sku': supplier_product.supplier_sku
        })
    except SupplierProduct.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Keine Lieferanteninformation gefunden'})
