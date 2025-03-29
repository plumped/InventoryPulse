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

from accessmanagement.decorators import permission_required
from core.models import Product, ProductWarehouse
from suppliers.models import Supplier, SupplierProduct
from inventory.models import Warehouse, StockMovement

from .models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt,
    PurchaseOrderReceiptItem, OrderSuggestion
)
from .forms import PurchaseOrderForm, ReceiveOrderForm
from .services import generate_order_suggestions
from .workflow import get_initial_order_status, check_auto_approval, can_approve_order


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

    # Systemwährung ermitteln
    from core.models import Currency
    system_currency = Currency.get_default_currency()

    # Umgerechnete Beträge berechnen
    for order in queryset:
        if order.supplier and order.supplier.default_currency and order.supplier.default_currency != system_currency:
            exchange_rate = order.supplier.default_currency.exchange_rate
            order.converted_total = order.total * exchange_rate
            order.system_currency = system_currency
        else:
            order.converted_total = None

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
        'system_currency': system_currency
    }

    return render(request, 'order/purchase_order_list.html', context)


@login_required
@permission_required('order', 'view')
def purchase_order_detail(request, pk):
    """Detailansicht einer Bestellung."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'created_by', 'approved_by')
        .prefetch_related('items__product', 'receipts', 'items__tax'),
        pk=pk
    )

    # Ermitteln, ob Benutzer bestimmte Aktionen durchführen darf
    can_edit = request.user.has_perm('order.edit') and order.status == 'draft'
    can_approve = can_approve_order(request.user, order) and order.status == 'pending'
    can_receive = request.user.has_perm('order.receive') and order.status in ['sent', 'partially_received']

    # Wareneingangshistorie abrufen
    receipts = order.receipts.select_related('received_by').prefetch_related('items__order_item__product',
                                                                             'items__warehouse')

    # Verfügbare Schnittstellen für diesen Lieferanten abrufen (für das Modal)
    interfaces = []
    if order.status == 'approved':
        from interfaces.models import SupplierInterface
        interfaces = SupplierInterface.objects.filter(
            supplier=order.supplier,
            is_active=True
        ).select_related('interface_type')

    # Systemwährung ermitteln
    from core.models import Currency
    system_currency = Currency.get_default_currency()

    # Die Währung für diese Bestellung (vom Lieferanten)
    supplier_currency = order.supplier.default_currency if order.supplier and order.supplier.default_currency else system_currency

    # Berechnen von umgerechneten Werten, wenn die Lieferantenwährung nicht die Systemwährung ist
    show_conversion = False
    if supplier_currency and supplier_currency != system_currency:
        show_conversion = True
        exchange_rate = supplier_currency.exchange_rate

        # Umrechnung der Bestellsummen
        order.converted_subtotal = order.subtotal * exchange_rate
        order.converted_total = order.total * exchange_rate
        order.converted_shipping_cost = order.shipping_cost * exchange_rate if order.shipping_cost else 0

        # Umrechnung der einzelnen Positionen
        for item in order.items.all():
            item.converted_unit_price = item.unit_price * exchange_rate
            item.converted_line_total = item.line_total * exchange_rate
            # Steuer pro Position umrechnen, falls vorhanden
            if hasattr(item, 'line_tax') and item.line_tax is not None:
                item.converted_line_tax = item.line_tax * exchange_rate

    # Prüfen, ob Produkte mit Chargen- oder Verfallsdatenverfolgung vorhanden sind
    product_ids = [item.product.id for item in order.items.all()]
    has_batch_products = Product.objects.filter(id__in=product_ids, has_batch_tracking=True).exists()
    has_expiry_products = Product.objects.filter(id__in=product_ids, has_expiry_tracking=True).exists()

    # Bei POST-Request (direkt aus dem Modal)
    if request.method == 'POST' and order.status == 'approved' and request.user.has_perm('order.edit'):
        interface_id = request.POST.get('interface_id')
        if interface_id:
            try:
                # Bestellung über die gewählte Schnittstelle senden
                from interfaces.services import send_order_via_interface
                result = send_order_via_interface(order.id, interface_id, request.user)

                if result:
                    # Bestellung als gesendet markieren
                    order.status = 'sent'
                    order.save(update_fields=['status'])

                    messages.success(request,
                                     f'Bestellung {order.order_number} wurde erfolgreich gesendet und als "Bestellt" markiert.')
                    return redirect('purchase_order_detail', pk=order.id)
                else:
                    messages.warning(request, f'Bestellung {order.order_number} konnte nicht gesendet werden.')
            except Exception as e:
                messages.error(request, f'Fehler beim Senden der Bestellung: {str(e)}')

    context = {
        'order': order,
        'can_edit': can_edit,
        'can_approve': can_approve,
        'can_receive': can_receive,
        'receipts': receipts,
        'interfaces': interfaces,
        'supplier_currency': supplier_currency,
        'system_currency': system_currency,
        'show_conversion': show_conversion,
        'has_batch_products': has_batch_products,
        'has_expiry_products': has_expiry_products
    }

    return render(request, 'order/purchase_order_detail.html', context)


@login_required
@permission_required('order', 'create')
def purchase_order_create(request):
    """Neue Bestellung erstellen."""
    # Systemeinstellungen abrufen
    try:
        from admin_dashboard.models import SystemSettings
        system_settings = SystemSettings.objects.first()
    except:
        system_settings = None

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Bestellung erstellen
                order = form.save(commit=False)
                order.created_by = request.user

                # Bestellnummer generieren
                today = date.today()

                # Präfix aus Systemeinstellungen oder Standardwert
                prefix = (system_settings.order_number_prefix if system_settings else "ORD-")
                order_number_prefix = f"{prefix}{today.strftime('%Y%m%d')}-"

                # Nächste Sequenznummer finden
                last_order = PurchaseOrder.objects.filter(
                    order_number__startswith=order_number_prefix
                ).order_by('-order_number').first()

                if last_order:
                    try:
                        last_seq = int(last_order.order_number.split('-')[-1])
                        next_seq = last_seq + 1
                    except ValueError:
                        next_seq = system_settings.next_order_number if system_settings else 1
                else:
                    # Wenn keine vorherige Bestellung, verwende Systemeinstellung oder 1
                    next_seq = system_settings.next_order_number if system_settings else 1

                # Bestellnummer generieren
                order.order_number = f"{order_number_prefix}{next_seq:03d}"

                # Systemeinstellungen aktualisieren (falls vorhanden)
                if system_settings:
                    system_settings.next_order_number = next_seq + 1
                    system_settings.save()

                # Initialen Status basierend auf Workflow-Einstellungen festlegen
                order.status = get_initial_order_status(order)

                order.save()

                # Positionen speichern
                process_order_items(request.POST, order)

                # Summen aktualisieren
                order.update_totals()

                # Auto-Approval prüfen
                if order.status == 'pending' and check_auto_approval(order):
                    order.status = 'approved'
                    order.approved_by = request.user
                    order.save()
                    messages.success(request, f'Bestellung {order.order_number} wurde automatisch genehmigt.')

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


# Aktualisiere die Funktion process_order_items in order/views.py, um die Steuer korrekt zu übernehmen

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
            tax_id_key = f'item_tax_id_{item_id}'
            currency_id_key = f'item_currency_id_{item_id}'

            if quantity_key in post_data and price_key in post_data:
                quantity = Decimal(post_data[quantity_key])
                price = Decimal(post_data[price_key])
                supplier_sku = post_data.get(supplier_sku_key, '')

                # Steuersatz ID, falls vorhanden
                tax_id = post_data.get(tax_id_key, None)

                # Währungs ID, falls vorhanden
                currency_id = post_data.get(currency_id_key, None)

                # Produkt abrufen
                product = get_object_or_404(Product, pk=product_id)

                # Steuersatz bestimmen
                from core.models import Tax
                tax = None
                if tax_id:
                    try:
                        tax = Tax.objects.get(pk=tax_id)
                    except Tax.DoesNotExist:
                        # Fallback zum Produkt-Steuersatz
                        tax = product.tax
                else:
                    # Fallback zum Produkt-Steuersatz
                    tax = product.tax

                # Währung bestimmen
                from core.models import Currency
                currency = None
                if currency_id:
                    try:
                        currency = Currency.objects.get(pk=currency_id)
                    except Currency.DoesNotExist:
                        # Fallback zur Standardwährung
                        currency = Currency.get_default_currency()
                else:
                    # Fallback zur Standardwährung
                    currency = Currency.get_default_currency()

                    # Falls ein Lieferantenprodukt mit einer bestimmten Währung existiert, diese verwenden
                    try:
                        supplier_product = SupplierProduct.objects.get(
                            supplier=order.supplier,
                            product=product
                        )
                        if supplier_product.currency:
                            currency = supplier_product.currency
                    except SupplierProduct.DoesNotExist:
                        pass

                if item_id.startswith('new_'):
                    # Neue Position erstellen mit der Steuer vom Produkt oder explizit gesetzter Steuer
                    PurchaseOrderItem.objects.create(
                        purchase_order=order,
                        product=product,
                        quantity_ordered=quantity,
                        unit_price=price,
                        supplier_sku=supplier_sku,
                        tax=tax,  # Steuersatz explizit setzen
                        currency=currency  # Währung explizit setzen
                    )
                else:
                    # Bestehende Position aktualisieren
                    try:
                        item_id_int = int(item_id)
                        if item_id_int in existing_items:
                            item = existing_items[item_id_int]

                            # Produkt und Menge aktualisieren
                            item.product = product
                            item.quantity_ordered = quantity
                            item.unit_price = price
                            item.supplier_sku = supplier_sku

                            # Explizit den Steuersatz aktualisieren
                            item.tax = tax

                            # Explizit die Währung aktualisieren
                            item.currency = currency

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

        # Auto-Approval prüfen
        if check_auto_approval(order):
            order.status = 'approved'
            order.approved_by = request.user
            order.save()
            messages.success(request,
                             f'Bestellung {order.order_number} wurde zur Genehmigung eingereicht und automatisch genehmigt.')
        else:
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

    # Prüfen, ob der Benutzer diese Bestellung genehmigen darf
    if not can_approve_order(request.user, order):
        messages.error(request,
                       f'Sie dürfen diese Bestellung nicht genehmigen, da Sie sie erstellt haben.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        order.status = 'approved'
        order.approved_by = request.user
        order.save()

        # E-Mail-Benachrichtigung senden, falls aktiviert
        try:
            from admin_dashboard.models import WorkflowSettings
            workflow_settings = WorkflowSettings.objects.first()
            if workflow_settings and workflow_settings.send_order_emails:
                # Hier Code zum Senden der E-Mail
                pass
        except:
            pass

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
        try:
            with transaction.atomic():
                # Wareneingang erstellen
                receipt = PurchaseOrderReceipt.objects.create(
                    purchase_order=order,
                    received_by=request.user,
                    notes=request.POST.get('notes', '')
                )

                # Für jede Position prüfen, ob Menge empfangen wurde
                items_received = False
                all_items_fully_received = True

                for item in order.items.all():
                    # Alle quantity-Felder für dieses Item finden (für multiple Batches)
                    quantity_fields = [key for key in request.POST.keys() if
                                       key.startswith(f'receive_quantity_{item.id}_')]
                    item_received_total = Decimal('0')

                    # Jede Batch-Zeile verarbeiten
                    for quantity_field in quantity_fields:
                        # Line-Index aus dem Feldnamen extrahieren (z.B. receive_quantity_5_0, receive_quantity_5_1)
                        line_index = quantity_field.split('_')[-1]
                        quantity_str = request.POST.get(quantity_field, '0')

                        try:
                            quantity = Decimal(quantity_str)
                        except:
                            quantity = Decimal('0')

                        if quantity > 0:
                            # Zugehörige Felder finden
                            warehouse_key = f'warehouse_{item.id}_{line_index}'
                            batch_key = f'batch_{item.id}_{line_index}'
                            expiry_key = f'expiry_{item.id}_{line_index}'

                            if warehouse_key in request.POST:
                                warehouse_id = request.POST[warehouse_key]
                                batch = request.POST.get(batch_key, '')
                                expiry = request.POST.get(expiry_key, '')

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

                                if batch and item.product.has_batch_tracking:
                                    from core.models import BatchNumber
                                    # Erstelle oder aktualisiere den Batch-Eintrag
                                    batch_obj, created = BatchNumber.objects.update_or_create(
                                        product=item.product,
                                        batch_number=batch,
                                        defaults={
                                            'warehouse': warehouse,
                                            'quantity': quantity,
                                            'expiry_date': receipt_item.expiry_date if hasattr(receipt_item,
                                                                                               'expiry_date') and receipt_item.expiry_date else None,
                                            'supplier': order.supplier,
                                            'notes': f'Batch aus Wareneingang: {order.order_number}'
                                        }
                                    )

                                    if not created:
                                        # Falls der Batch bereits existiert, Menge erhöhen
                                        batch_obj.quantity += quantity
                                        batch_obj.save()

                                # Bestandsbewegung erstellen
                                StockMovement.objects.create(
                                    product=item.product,
                                    warehouse=warehouse,
                                    quantity=quantity,
                                    movement_type='in',
                                    reference=f'Wareneingang: {order.order_number}',
                                    notes=f'Erhaltene Menge: {quantity}, Charge: {batch}',
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

                                # Gesamtmenge für dieses Item aktualisieren
                                item_received_total += quantity
                                items_received = True

                    # Bestellposition aktualisieren mit der Gesamtmenge aller Batches
                    if item_received_total > 0:
                        item.quantity_received += item_received_total
                        item.save()

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

        except Exception as e:
            import traceback
            print(traceback.format_exc())  # Print detailed error to console
            messages.error(request, f'Fehler beim Speichern des Wareneingangs: {str(e)}')

    # Create a simple form just for the notes field
    form = ReceiveOrderForm()

    # Verfügbare Lager abrufen
    warehouses = Warehouse.objects.filter(is_active=True)

    # Prüfen, ob Produkte Batch- oder Verfallsdatum-Tracking benötigen
    has_batch_products = any(item.product.has_batch_tracking for item in order.items.all())
    has_expiry_products = any(item.product.has_expiry_tracking for item in order.items.all())

    context = {
        'order': order,
        'form': form,
        'warehouses': warehouses,
        'has_batch_products': has_batch_products,
        'has_expiry_products': has_expiry_products,
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


# In order/views.py - order_suggestions View aktualisieren

@login_required
@permission_required('order', 'view')
def order_suggestions(request):
    """Zeigt Bestellvorschläge basierend auf kritischen Beständen."""

    # Automatisch alle Bestellvorschläge aktualisieren
    # Hierfür können wir direkt die bereits vorhandene Funktion nutzen
    suggestion_count = generate_order_suggestions()

    if suggestion_count > 0:
        messages.info(request, f'Bestellvorschläge wurden automatisch aktualisiert: {suggestion_count} Vorschläge.')

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


# Füge diese Methode in der order/views.py hinzu, um manuelle Produkte in der create_orders_from_suggestions Funktion zu verarbeiten

@login_required
@permission_required('order', 'create')
# Update in order/views.py - create_orders_from_suggestions function
# Add this code to handle expected delivery date calculation

def create_orders_from_suggestions(request):
    """Erstellt Bestellungen basierend auf ausgewählten Bestellvorschlägen und manuell hinzugefügten Produkten."""
    if request.method == 'POST':
        # Ausgewählte Vorschläge ermitteln
        selected_ids = request.POST.getlist('selected_suggestions')
        # Manuell hinzugefügte Produkte ermitteln
        manual_products = request.POST.getlist('manual_products[]')

        if not selected_ids and not manual_products:
            messages.warning(request, 'Es wurden keine Artikel ausgewählt.')
            return redirect('order_suggestions')

        # Vorschläge nach Lieferant gruppieren
        suggestions_by_supplier = {}

        # Bestehende Vorschläge verarbeiten
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

        # Manuell hinzugefügte Produkte verarbeiten
        for product_id in manual_products:
            try:
                product = Product.objects.get(pk=product_id)
                supplier_id = request.POST.get(f'manual_supplier_{product_id}')
                quantity_str = request.POST.get(f'manual_quantity_{product_id}', '1')

                if not supplier_id:
                    continue

                try:
                    quantity = Decimal(quantity_str)
                except ValueError:
                    quantity = Decimal('1')

                # Nur hinzufügen, wenn Menge > 0
                if quantity <= 0:
                    continue

                supplier = Supplier.objects.get(pk=supplier_id)

                if supplier not in suggestions_by_supplier:
                    suggestions_by_supplier[supplier] = []

                suggestions_by_supplier[supplier].append({
                    'product': product,
                    'quantity': quantity
                })
            except (Product.DoesNotExist, Supplier.DoesNotExist, ValueError):
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
                    # Systemeinstellungen abrufen für Bestellnummer-Präfix
                    try:
                        from admin_dashboard.models import SystemSettings
                        system_settings = SystemSettings.objects.first()
                        prefix = system_settings.order_number_prefix if system_settings else "ORD-"
                        next_seq = system_settings.next_order_number if system_settings else 1
                    except:
                        # Fallback, wenn keine Systemeinstellungen vorhanden sind
                        prefix = "ORD-"
                        next_seq = 1

                    # Bestellnummer generieren
                    today = date.today()
                    order_number_prefix = f"{prefix}{today.strftime('%Y%m%d')}-"

                    # Nächste Sequenznummer finden
                    last_order = PurchaseOrder.objects.filter(
                        order_number__startswith=order_number_prefix
                    ).order_by('-order_number').first()

                    if last_order:
                        try:
                            last_seq = int(last_order.order_number.split('-')[-1])
                            next_seq = last_seq + 1
                        except ValueError:
                            pass  # Verwende den Standardwert aus den Systemeinstellungen

                    order_number = f"{order_number_prefix}{next_seq:03d}"

                    # Ermittle den erwarteten Liefertermin basierend auf den Lieferzeiten der Produkte
                    # Standardwert aus den Systemeinstellungen oder 7 Tage
                    default_lead_time = 7
                    try:
                        if system_settings and hasattr(system_settings, 'default_lead_time'):
                            default_lead_time = system_settings.default_lead_time
                    except:
                        pass

                    # Ermittle die längste Lieferzeit für alle Produkte des Lieferanten
                    max_lead_time = default_lead_time
                    for item in items:
                        try:
                            supplier_product = SupplierProduct.objects.get(
                                supplier=supplier,
                                product=item['product']
                            )
                            if supplier_product.lead_time_days and supplier_product.lead_time_days > max_lead_time:
                                max_lead_time = supplier_product.lead_time_days
                        except SupplierProduct.DoesNotExist:
                            continue

                    # Berechne das erwartete Lieferdatum
                    expected_delivery = today + timedelta(days=max_lead_time)

                    order = PurchaseOrder.objects.create(
                        supplier=supplier,
                        created_by=request.user,
                        status='draft',
                        order_number=order_number,
                        expected_delivery=expected_delivery  # Setze den erwarteten Liefertermin
                    )

                    # Systemeinstellungen aktualisieren
                    if 'system_settings' in locals() and system_settings:
                        system_settings.next_order_number = next_seq + 1
                        system_settings.save()

                    orders_created += 1

                # Positionen hinzufügen oder aktualisieren
                for item in items:
                    # Prüfen, ob das Produkt bereits in der Bestellung ist
                    existing_item = PurchaseOrderItem.objects.filter(
                        purchase_order=order,
                        product=item['product']
                    ).first()

                    # Lieferantenpreis und Währung ermitteln
                    unit_price = Decimal('0.00')
                    supplier_sku = ''
                    currency = None

                    try:
                        supplier_product = SupplierProduct.objects.get(
                            supplier=supplier,
                            product=item['product']
                        )
                        unit_price = supplier_product.purchase_price
                        supplier_sku = supplier_product.supplier_sku

                        # Währung aus dem SupplierProduct oder vom Supplier verwenden
                        currency = supplier_product.currency or supplier.default_currency

                        # Wenn keine Währung definiert ist, Standardwährung verwenden
                        if not currency:
                            from core.models import Currency
                            currency = Currency.get_default_currency()

                    except SupplierProduct.DoesNotExist:
                        # Wenn kein Lieferantenprodukt existiert, verwende die Standardwährung des Lieferanten
                        if supplier.default_currency:
                            currency = supplier.default_currency
                        else:
                            from core.models import Currency
                            currency = Currency.get_default_currency()

                    if existing_item:
                        # Menge erhöhen und Währung aktualisieren, falls notwendig
                        existing_item.quantity_ordered += item['quantity']

                        # Währung aktualisieren, falls nicht gesetzt
                        if not existing_item.currency:
                            existing_item.currency = currency

                        existing_item.save()
                    else:
                        # Neue Position erstellen
                        PurchaseOrderItem.objects.create(
                            purchase_order=order,
                            product=item['product'],
                            quantity_ordered=item['quantity'],
                            unit_price=unit_price,
                            supplier_sku=supplier_sku,
                            currency=currency,  # Währung mit angeben
                            # Steuersatz vom Produkt übernehmen
                            tax=item['product'].tax
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
    """AJAX-Endpunkt zum Abrufen des Lieferantenpreises und der SKU für ein Produkt."""
    product_id = request.GET.get('product_id')
    supplier_id = request.GET.get('supplier_id')

    if not product_id or not supplier_id:
        return JsonResponse(
            {'success': False, 'message': 'Produkt- und Lieferanten-ID erforderlich'})

    try:
        # Lieferanten-Produkt-Informationen abrufen
        supplier_product = SupplierProduct.objects.get(
            product_id=product_id,
            supplier_id=supplier_id
        )

        # Produkt-Informationen für Steuersatz abrufen
        product = Product.objects.get(pk=product_id)

        # Währungs-Informationen abrufen
        from core.models import Currency
        default_currency = Currency.get_default_currency()
        currency_info = {
            'id': supplier_product.currency.id if supplier_product.currency else (
                default_currency.id if default_currency else None),
            'code': supplier_product.currency.code if supplier_product.currency else (
                default_currency.code if default_currency else ''),
            'symbol': supplier_product.currency.symbol if supplier_product.currency else (
                default_currency.symbol if default_currency else '')
        }

        return JsonResponse({
            'success': True,
            'price': float(supplier_product.purchase_price),
            'supplier_sku': supplier_product.supplier_sku,
            'tax_rate': float(product.get_tax_rate) if hasattr(product, 'get_tax_rate') else 0,
            'tax_id': product.tax.id if product.tax else None,
            'unit': product.unit,
            'currency': currency_info
        })
    except SupplierProduct.DoesNotExist:
        # Wenn keine spezifische Lieferanten-Produkt-Beziehung existiert,
        # geben wir trotzdem die Produktinformationen zurück
        try:
            product = Product.objects.get(pk=product_id)
            # Standardwährung abrufen
            from core.models import Currency
            default_currency = Currency.get_default_currency()
            currency_info = {
                'id': default_currency.id if default_currency else None,
                'code': default_currency.code if default_currency else '',
                'symbol': default_currency.symbol if default_currency else ''
            }

            return JsonResponse({
                'success': True,
                'price': None,  # Kein spezifischer Preis vorhanden
                'supplier_sku': '',  # Keine Lieferanten-SKU vorhanden
                'tax_rate': float(product.get_tax_rate) if hasattr(product, 'get_tax_rate') else 0,
                'tax_id': product.tax.id if product.tax else None,
                'unit': product.unit,
                'currency': currency_info,
                'message': 'Keine spezifischen Lieferanteninformationen gefunden'
            })
        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Produkt nicht gefunden'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler: {str(e)}'
        })

@login_required
@permission_required('order', 'edit')
def bulk_send_orders(request):
    """Sendet mehrere ausgewählte Bestellungen über die jeweiligen Standard-Schnittstellen."""
    if request.method != 'POST':
        return redirect('purchase_order_list')

    # Ausgewählte Bestellungen abrufen
    selected_ids = request.POST.getlist('selected_orders')

    if not selected_ids:
        messages.warning(request, 'Keine Bestellungen ausgewählt.')
        return redirect('purchase_order_list')

    # Nur genehmigte Bestellungen filtern
    orders = PurchaseOrder.objects.filter(
        id__in=selected_ids,
        status='approved'
    )

    # Ergebnisse verfolgen
    results = {
        'success': [],
        'failed': []
    }

    # Jede Bestellung über ihre Standard-Schnittstelle senden
    for order in orders:
        try:
            from interfaces.services import send_order_via_interface

            # Versuch, die Bestellung über die Standard-Schnittstelle zu senden
            result = send_order_via_interface(order.id, None, request.user)  # None = use default interface

            if result:  # Nur bei erfolgreichem Versand als gesendet markieren
                # Bestellung als gesendet markieren
                order.status = 'sent'
                order.save(update_fields=['status'])  # Nur das geänderte Feld aktualisieren
                results['success'].append(order)
            else:
                results['failed'].append((order, 'Unbekannter Fehler beim Senden'))

        except Exception as e:
            results['failed'].append((order, str(e)))

    # Erfolgsmeldungen
    if results['success']:
        order_numbers = ', '.join([o.order_number for o in results['success']])
        messages.success(
            request,
            f"{len(results['success'])} Bestellung{'en' if len(results['success']) != 1 else ''} erfolgreich gesendet: {order_numbers}"
        )

    # Fehlermeldungen
    if results['failed']:
        error_messages = '<br>'.join([f"{o[0].order_number}: {o[1]}" for o in results['failed']])
        messages.error(
            request,
            f"{len(results['failed'])} Bestellung{'en' if len(results['failed']) != 1 else ''} konnten nicht gesendet werden:<br>{error_messages}",
            extra_tags='safe'
        )

    return redirect('purchase_order_list')


@login_required
@permission_required('order', 'edit')
def purchase_order_receipt_edit(request, pk, receipt_id):
    """Edit a purchase order receipt."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    receipt = get_object_or_404(PurchaseOrderReceipt, pk=receipt_id, purchase_order=order)

    # Only receipts for orders in partially_received or received status can be edited
    if order.status not in ['partially_received', 'received']:
        messages.error(request,
                       f'Wareneingang kann nicht bearbeitet werden, da die Bestellung im Status "{order.get_status_display()}" ist.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        # Process form submission
        notes = request.POST.get('notes', '')

        with transaction.atomic():
            # Update receipt notes
            receipt.notes = notes
            receipt.save()

            # Process each receipt item
            for item in receipt.items.all():
                # Get updated values from form
                quantity_key = f'quantity_{item.id}'
                warehouse_key = f'warehouse_{item.id}'
                batch_key = f'batch_{item.id}'
                expiry_key = f'expiry_{item.id}'

                if quantity_key in request.POST:
                    try:
                        new_quantity = Decimal(request.POST.get(quantity_key))
                        old_quantity = item.quantity_received

                        # Only process if quantity changed
                        if new_quantity != old_quantity:
                            # Update the quantity difference in the stock
                            quantity_diff = new_quantity - old_quantity

                            # Update the receipt item quantity
                            item.quantity_received = new_quantity

                            # Update warehouse if changed
                            if warehouse_key in request.POST:
                                new_warehouse_id = request.POST.get(warehouse_key)
                                new_warehouse = get_object_or_404(Warehouse, pk=new_warehouse_id)

                                if new_warehouse.id != item.warehouse.id:
                                    # First, reverse the stock movement in the old warehouse
                                    StockMovement.objects.create(
                                        product=item.order_item.product,
                                        warehouse=item.warehouse,
                                        quantity=-old_quantity,
                                        movement_type='adj',
                                        reference=f'Wareneingang korrigiert: {order.order_number}',
                                        notes=f'Wareneingang in anderes Lager verschoben',
                                        created_by=request.user
                                    )

                                    # Update ProductWarehouse for old warehouse
                                    try:
                                        pw_old = ProductWarehouse.objects.get(
                                            product=item.order_item.product,
                                            warehouse=item.warehouse
                                        )
                                        pw_old.quantity -= old_quantity
                                        pw_old.save()
                                    except ProductWarehouse.DoesNotExist:
                                        pass  # Should not happen, but just in case

                                    # Create stock movement in new warehouse
                                    StockMovement.objects.create(
                                        product=item.order_item.product,
                                        warehouse=new_warehouse,
                                        quantity=new_quantity,
                                        movement_type='in',
                                        reference=f'Wareneingang verschoben: {order.order_number}',
                                        notes=f'Von {item.warehouse.name} nach {new_warehouse.name}',
                                        created_by=request.user
                                    )

                                    # Update ProductWarehouse for new warehouse
                                    pw_new, created = ProductWarehouse.objects.get_or_create(
                                        product=item.order_item.product,
                                        warehouse=new_warehouse,
                                        defaults={'quantity': 0}
                                    )
                                    pw_new.quantity += new_quantity
                                    pw_new.save()

                                    # Update item's warehouse
                                    item.warehouse = new_warehouse
                                else:
                                    # Same warehouse, just update the quantity
                                    StockMovement.objects.create(
                                        product=item.order_item.product,
                                        warehouse=item.warehouse,
                                        quantity=quantity_diff,
                                        movement_type='adj',
                                        reference=f'Wareneingang korrigiert: {order.order_number}',
                                        notes=f'Korrektur von {old_quantity} auf {new_quantity}',
                                        created_by=request.user
                                    )

                                    # Update ProductWarehouse
                                    pw, created = ProductWarehouse.objects.get_or_create(
                                        product=item.order_item.product,
                                        warehouse=item.warehouse,
                                        defaults={'quantity': 0}
                                    )
                                    pw.quantity += quantity_diff
                                    pw.save()
                            else:
                                # No warehouse change, just update quantity
                                StockMovement.objects.create(
                                    product=item.order_item.product,
                                    warehouse=item.warehouse,
                                    quantity=quantity_diff,
                                    movement_type='adj',
                                    reference=f'Wareneingang korrigiert: {order.order_number}',
                                    notes=f'Korrektur von {old_quantity} auf {new_quantity}',
                                    created_by=request.user
                                )

                                # Update ProductWarehouse
                                pw, created = ProductWarehouse.objects.get_or_create(
                                    product=item.order_item.product,
                                    warehouse=item.warehouse,
                                    defaults={'quantity': 0}
                                )
                                pw.quantity += quantity_diff
                                pw.save()

                            # Update batch number if applicable
                            if batch_key in request.POST:
                                item.batch_number = request.POST.get(batch_key)

                            # Update expiry date if applicable
                            if expiry_key in request.POST and request.POST.get(expiry_key):
                                try:
                                    item.expiry_date = request.POST.get(expiry_key)
                                except ValueError:
                                    pass  # Invalid date format, ignore

                            # Save the receipt item
                            item.save()

                            # Update the order item's received quantity
                            order_item = item.order_item

                            # Recalculate total received quantity for this order item from all receipts
                            from django.db.models import Sum
                            total_received = PurchaseOrderReceiptItem.objects.filter(
                                order_item=order_item
                            ).aggregate(
                                total=Sum('quantity_received')
                            )['total'] or 0

                            # Update the order item
                            order_item.quantity_received = total_received
                            order_item.save()

                    except (ValueError, TypeError) as e:
                        messages.error(request,
                                       f'Ungültige Menge für Position {item.order_item.product.name}: {str(e)}')

            # Recalculate order status based on updated receipt items
            all_items_received = True
            any_items_received = False

            for order_item in order.items.all():
                if order_item.quantity_received >= order_item.quantity_ordered:
                    any_items_received = True
                else:
                    all_items_received = False
                    if order_item.quantity_received > 0:
                        any_items_received = True

            if all_items_received:
                order.status = 'received'
            elif any_items_received:
                order.status = 'partially_received'
            else:
                order.status = 'sent'

            order.save()

            messages.success(request,
                             f'Wareneingang für Bestellung {order.order_number} wurde erfolgreich aktualisiert.')
            return redirect('purchase_order_detail', pk=order.pk)

    # For GET requests, prepare form
    warehouses = Warehouse.objects.filter(is_active=True)

    # Prepare items data with the right field names matching the template
    items_data = []

    # Check for any products requiring batch or expiry tracking
    any_batch_products = False
    any_expiry_products = False

    for item in receipt.items.all():
        product = item.order_item.product

        # Check for batch and expiry tracking
        if product.has_batch_tracking:
            any_batch_products = True
        if product.has_expiry_tracking:
            any_expiry_products = True

        items_data.append({
            'id': item.id,
            'product': product,
            'quantity': item.quantity_received,
            'warehouse': item.warehouse,
            'batch_number': item.batch_number,
            'expiry_date': item.expiry_date.isoformat() if item.expiry_date else None,
            'has_batch_tracking': product.has_batch_tracking,
            'has_expiry_tracking': product.has_expiry_tracking
        })

    context = {
        'order': order,
        'receipt': receipt,
        'items': items_data,
        'warehouses': warehouses,
        'any_batch_products': any_batch_products,
        'any_expiry_products': any_expiry_products
    }

    return render(request, 'order/purchase_order_receipt_edit.html', context)


@login_required
@permission_required('order', 'delete')
def purchase_order_receipt_delete(request, pk, receipt_id):
    """Delete a purchase order receipt."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    receipt = get_object_or_404(PurchaseOrderReceipt, pk=receipt_id, purchase_order=order)

    # Only receipts for orders in partially_received or received status can be deleted
    if order.status not in ['partially_received', 'received']:
        messages.error(request,
                       f'Wareneingang kann nicht gelöscht werden, da die Bestellung im Status "{order.get_status_display()}" ist.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        with transaction.atomic():
            # Reverse all stock movements and update product warehouse quantities
            for item in receipt.items.all():
                # Reverse stock movement
                StockMovement.objects.create(
                    product=item.order_item.product,
                    warehouse=item.warehouse,
                    quantity=-item.quantity_received,
                    movement_type='adj',
                    reference=f'Wareneingang gelöscht: {order.order_number}',
                    notes=f'Wareneingang vom {receipt.receipt_date} gelöscht',
                    created_by=request.user
                )

                # Update product warehouse
                pw, created = ProductWarehouse.objects.get_or_create(
                    product=item.order_item.product,
                    warehouse=item.warehouse,
                    defaults={'quantity': 0}
                )
                pw.quantity -= item.quantity_received
                pw.save()

                # Update order item received quantity
                order_item = item.order_item
                order_item.quantity_received -= item.quantity_received
                order_item.save()

            # Delete the receipt
            receipt.delete()

            # Update order status based on remaining receipts
            all_items_received = True
            any_items_received = False

            for order_item in order.items.all():
                if order_item.quantity_received >= order_item.quantity_ordered:
                    any_items_received = True
                else:
                    all_items_received = False
                    if order_item.quantity_received > 0:
                        any_items_received = True

            if all_items_received:
                order.status = 'received'
            elif any_items_received:
                order.status = 'partially_received'
            else:
                order.status = 'sent'

            order.save()

            messages.success(request, f'Wareneingang für Bestellung {order.order_number} wurde erfolgreich gelöscht.')

        return redirect('purchase_order_detail', pk=order.pk)

    context = {
        'order': order,
        'receipt': receipt,
    }

    return render(request, 'order/purchase_order_receipt_confirm_delete.html', context)


# Add this function to order/views.py

# Add this function to order/views.py

@login_required
def get_supplier_products_list(request):
    """AJAX-Endpunkt für die Suche nach Produkten eines Lieferanten."""
    supplier_id = request.GET.get('supplier_id')
    search_query = request.GET.get('q', '')
    page = int(request.GET.get('page', 1))
    page_size = 50  # Increased number of results per page

    if not supplier_id:
        return JsonResponse({
            'success': False,
            'message': 'Lieferanten-ID erforderlich'
        })

    try:
        # Base query - products that have a relationship with this supplier
        queryset = SupplierProduct.objects.filter(
            supplier_id=supplier_id
        ).select_related('product', 'product__tax')

        # Apply search filter if provided
        if search_query:
            queryset = queryset.filter(
                Q(product__name__icontains=search_query) |
                Q(product__sku__icontains=search_query) |
                Q(supplier_sku__icontains=search_query)
            )

        # Calculate total and paginate
        total_count = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size

        # Get the paginated results
        supplier_products = queryset[start:end]

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
            'products': products_data,
            'total': total_count,
            'more': (page * page_size) < total_count  # Whether there are more results
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler: {str(e)}'
        })


# Add this to suppliers/views.py

# Add this function to order/views.py

@login_required
def get_supplier_products_list(request):
    """AJAX-Endpunkt für die Suche nach Produkten eines Lieferanten."""
    supplier_id = request.GET.get('supplier_id')
    search_query = request.GET.get('q', '')
    page = int(request.GET.get('page', 1))
    page_size = 100  # Increased number of results per page for better matches

    if not supplier_id:
        return JsonResponse({
            'success': False,
            'message': 'Lieferanten-ID erforderlich'
        })

    try:
        # Base query - products that have a relationship with this supplier
        queryset = SupplierProduct.objects.filter(
            supplier_id=supplier_id
        ).select_related('product', 'product__tax')

        # Apply search filter if provided
        if search_query:
            # Check if search query is an exact SKU match
            exact_sku_match = queryset.filter(
                Q(product__sku__iexact=search_query) |
                Q(supplier_sku__iexact=search_query)
            )

            # If we have an exact match, just return that
            if exact_sku_match.exists():
                queryset = exact_sku_match
            else:
                # Otherwise do a partial match search
                queryset = queryset.filter(
                    Q(product__name__icontains=search_query) |
                    Q(product__sku__icontains=search_query) |
                    Q(supplier_sku__icontains=search_query)
                )

        # Calculate total and paginate
        total_count = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size

        # Get the paginated results
        supplier_products = queryset[start:end]

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
            'products': products_data,
            'total': total_count,
            'more': (page * page_size) < total_count  # Whether there are more results
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler: {str(e)}'
        })


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