import uuid
from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q, Sum, F, Count, Case, When, Value, IntegerField
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.urls import reverse
from django.db import models


from accessmanagement.decorators import permission_required
from core.models import Product, ProductWarehouse, Currency
from rma.models import RMA
from suppliers.models import Supplier, SupplierProduct
from inventory.models import Warehouse, StockMovement

from .models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt,
    PurchaseOrderReceiptItem, OrderSuggestion, OrderTemplate, OrderTemplateItem, OrderSplit, OrderSplitItem,
    PurchaseOrderComment
)
from .forms import PurchaseOrderForm, ReceiveOrderForm, OrderSplitForm, OrderSplitItemFormSet
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

    # Datum für farbliche Hervorhebung berechnen
    today_date = date.today()
    soon_date = today_date + timedelta(days=7)  # 7 Tage in der Zukunft für "bald fällig"

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
        'system_currency': system_currency,
        'today_date': today_date,  # Heutiges Datum für Template
        'soon_date': soon_date     # Datum für "bald fällig"
    }

    return render(request, 'order/purchase_order_list.html', context)


@login_required
@permission_required('order', 'view')
def purchase_order_detail(request, pk):
    """
    Angepasste Funktion für die Bestelldetailseite mit verbesserter Darstellung von Teillieferungen.
    """
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'created_by', 'approved_by')
        .prefetch_related('items__product', 'receipts', 'items__tax'),
        pk=pk
    )

    # Teillieferungen mit zusätzlichen Informationen laden
    splits = []
    for split in order.splits.all():
        # Anzahl der bereits empfangenen Artikel berechnen
        received_items_count = 0
        for receipt in split.receipts.all():
            received_items_count += receipt.items.count()

        splits.append({
            'split': split,
            'received_items_count': received_items_count,
            'total_items_count': split.items.count(),
            'completion_percentage': int(received_items_count / max(split.items.count(), 1) * 100)
        })

    total_ordered = Decimal('0')
    total_received = Decimal('0')

    for item in order.items.all():
        if not item.is_canceled:  # Stornierte Positionen ausschließen
            # Effektive Menge (unter Berücksichtigung von Teilstornierungen)
            ordered_qty = item.quantity_ordered - item.canceled_quantity
            total_ordered += ordered_qty
            total_received += min(item.quantity_received, ordered_qty)  # Nicht mehr als bestellt zählen

    order_completion = {
        'percentage': int((total_received / total_ordered * 100) if total_ordered else 0),
        'received_quantity': total_received,
        'total_quantity': total_ordered
    }

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

    # Daten für die Workflow-Visualization
    progress_percentage = 0
    status_weights = {
        'draft': 0,
        'pending': 20,
        'approved': 40,
        'sent': 60,
        'partially_received': 80,
        'received': 100,
        'cancelled': 0  # Sonderfall
    }
    progress_percentage = status_weights.get(order.status, 0)

    # Datum für farbliche Hervorhebung des Lieferdatums
    today_date = date.today()
    soon_date = today_date + timedelta(days=7)  # 7 Tage in der Zukunft für "bald fällig"

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

                    # Versuchen, die längste lead_time_days für Produkte in dieser Bestellung zu finden
                    max_lead_time = 7  # Standardwert, falls keine Lieferantenprodukte gefunden werden
                    for item in order.items.all():
                        try:
                            supplier_product = SupplierProduct.objects.get(
                                supplier=order.supplier,
                                product=item.product
                            )
                            if supplier_product.lead_time_days and supplier_product.lead_time_days > max_lead_time:
                                max_lead_time = supplier_product.lead_time_days
                        except SupplierProduct.DoesNotExist:
                            continue

                    # soon_date auf heute + längste lead_time_days setzen
                    soon_date = date.today() + timedelta(days=max_lead_time)
                    order.soon_date = soon_date

                    # expected_delivery auf soon_date setzen
                    order.expected_delivery = soon_date

                    # Bestellstatus und Lieferdatum speichern
                    order.save()

                    messages.success(request,
                                     f'Bestellung {order.order_number} wurde erfolgreich gesendet und als "Bestellt" markiert.')
                    return redirect('purchase_order_detail', pk=order.id)
                else:
                    messages.warning(request, f'Bestellung {order.order_number} konnte nicht gesendet werden.')
            except Exception as e:
                messages.error(request, f'Fehler beim Senden der Bestellung: {str(e)}')

    context = {
        'order': order,
        'order_completion': order_completion,
        'splits': splits,
        'can_edit': can_edit,
        'can_approve': can_approve,
        'can_receive': can_receive,
        'receipts': receipts,
        'interfaces': interfaces,
        'supplier_currency': supplier_currency,
        'system_currency': system_currency,
        'show_conversion': show_conversion,
        'has_batch_products': has_batch_products,
        'has_expiry_products': has_expiry_products,
        'progress_percentage': progress_percentage,
        'today_date': today_date,
        'soon_date': soon_date,
        'expected_delivery': order.expected_delivery,
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
    """
    Vereinheitlichte Funktion für Wareneingang, die sowohl normale als auch Teillieferungen unterstützt.
    """
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Nur Bestellungen im Status "bestellt" oder "teilweise erhalten" können Wareneingänge haben
    if order.status not in ['sent', 'partially_received']:
        messages.error(request,
                       'Wareneingang kann nicht erfasst werden, da die Bestellung nicht im Status "Bestellt" oder "Teilweise erhalten" ist.')
        return redirect('purchase_order_detail', pk=order.pk)

    # Verfügbare Lager abrufen
    warehouses = Warehouse.objects.filter(is_active=True)

    # Nur nicht vollständig erhaltene und nicht stornierte Positionen anzeigen
    items = order.items.filter(
        quantity_received__lt=F('quantity_ordered'),
        status__in=['active', 'partially_canceled']
    ).select_related('product')

    # Überprüfen, ob Produkte Batch- oder Verfallsdatum-Tracking benötigen
    has_batch_products = any(item.product.has_batch_tracking for item in items)
    has_expiry_products = any(item.product.has_expiry_tracking for item in items)

    if request.method == 'POST':
        is_complete_delivery = True
        for item in items:
            quantity_key = f'receive_quantity_{item.id}'
            quantity = Decimal(request.POST.get(quantity_key, '0'))
            remaining = item.quantity_ordered - item.quantity_received

            if quantity < remaining:
                is_complete_delivery = False
                break

        # Prüfen, ob eine existierende Teillieferung verwendet werden soll
        use_existing_split = request.POST.get('use_existing_split') == 'on'
        existing_split_id = request.POST.get('existing_split_id')

        # Prüfen, ob eine neue Teillieferung erstellt werden soll
        create_split = request.POST.get('create_split') == 'yes' and not is_complete_delivery and not use_existing_split
        split_name = request.POST.get('split_name', '')
        expected_delivery = request.POST.get('expected_delivery', None)

        # Defekte Artikel aus dem Formular abrufen
        defective_items = []
        defective_items_data = request.POST.get('defective_items', '')
        if defective_items_data:
            try:
                import json
                defective_items = json.loads(defective_items_data)
            except (json.JSONDecodeError, ValueError):
                # Fehler beim Parsen ignorieren
                pass

        try:
            with transaction.atomic():
                # Bei Bedarf eine neue Teillieferung anlegen oder eine bestehende verwenden
                split = None

                if use_existing_split and existing_split_id:
                    # Bestehende Teillieferung verwenden
                    try:
                        split = OrderSplit.objects.get(pk=existing_split_id, purchase_order=order)
                        # Status auf 'received' setzen, da wir Waren für diese Teillieferung empfangen
                        split.status = 'received'
                        split.save()
                    except OrderSplit.DoesNotExist:
                        messages.error(request, 'Die ausgewählte Teillieferung konnte nicht gefunden werden.')
                        return redirect('purchase_order_receive', pk=order.pk)
                elif create_split:
                    # Neue Teillieferung erstellen
                    split = OrderSplit.objects.create(
                        purchase_order=order,
                        name=split_name or f"Teillieferung {timezone.now().strftime('%d.%m.%Y')}",
                        expected_delivery=expected_delivery if expected_delivery else None,
                        status='received',  # Da wir direkt den Wareneingang erfassen
                        created_by=request.user
                    )

                # Wareneingang erstellen
                receipt = PurchaseOrderReceipt.objects.create(
                    purchase_order=order,
                    received_by=request.user,
                    notes=request.POST.get('notes', ''),
                    order_split=split  # Verknüpfung mit der Teillieferung (falls vorhanden)
                )

                # Flag, um zu prüfen, ob Artikel empfangen wurden
                items_received = False
                # Flag, um zu prüfen, ob eine Teillieferung vorliegt
                is_partial_receipt = False

                # Für jede Position prüfen, ob Menge empfangen wurde
                for item in items:
                    # Formularfelder für diese Position finden
                    quantity_key = f'receive_quantity_{item.id}'
                    warehouse_key = f'warehouse_{item.id}'
                    batch_key = f'batch_{item.id}'
                    expiry_key = f'expiry_{item.id}'
                    has_quality_issue_key = f'has_quality_issue_{item.id}'

                    if quantity_key in request.POST:
                        try:
                            quantity = Decimal(request.POST[quantity_key])
                        except:
                            quantity = Decimal('0')

                        if quantity > 0:
                            # Prüfen, ob dies eine Teillieferung ist
                            remaining = item.quantity_ordered - item.quantity_received
                            if quantity < remaining:
                                is_partial_receipt = True

                            # Zielwarenhaus abrufen
                            warehouse_id = request.POST.get(warehouse_key)
                            warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

                            # Chargen- und Verfallsdatum-Informationen
                            batch = request.POST.get(batch_key, '')
                            expiry_date = None
                            if expiry_key in request.POST and request.POST.get(expiry_key):
                                try:
                                    from datetime import date
                                    expiry_date = date.fromisoformat(request.POST.get(expiry_key))
                                except ValueError:
                                    pass

                            # Wareneingangposition erstellen
                            receipt_item = PurchaseOrderReceiptItem.objects.create(
                                receipt=receipt,
                                order_item=item,
                                quantity_received=quantity,
                                warehouse=warehouse,
                                batch_number=batch,
                                expiry_date=expiry_date
                            )

                            # Batch verarbeiten, falls erforderlich
                            if batch and item.product.has_batch_tracking:
                                from core.models import BatchNumber
                                # Erstelle oder aktualisiere Batch-Eintrag
                                batch_obj, created = BatchNumber.objects.update_or_create(
                                    product=item.product,
                                    batch_number=batch,
                                    warehouse=warehouse,
                                    defaults={
                                        'quantity': quantity,
                                        'expiry_date': expiry_date,
                                        'supplier': order.supplier,
                                        'notes': f'Batch aus Wareneingang: {order.order_number}'
                                    }
                                )

                                if not created:
                                    # Falls Batch bereits existiert, Menge erhöhen
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

                            # Produktbestand im Lager aktualisieren
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

                            # Wenn wir eine Teillieferung haben und diese neu erstellt wurde,
                            # auch die entsprechende Position anlegen
                            if split and create_split:
                                OrderSplitItem.objects.create(
                                    order_split=split,
                                    order_item=item,
                                    quantity=quantity
                                )
                            # Wenn wir eine bestehende Teillieferung verwenden,
                            # prüfen, ob ein SplitItem existiert und aktualisieren oder erstellen
                            elif split and use_existing_split:
                                # Prüfen, ob bereits ein Split-Item für diesen Order-Item existiert
                                try:
                                    split_item = OrderSplitItem.objects.get(
                                        order_split=split,
                                        order_item=item
                                    )
                                    # Hier NICHT die Menge erhöhen, sondern die Gesamtmenge aktualisieren
                                    if quantity > 0:
                                        # Nur aktualisieren, wenn eine Menge eingegeben wurde
                                        split_item.quantity = quantity
                                        split_item.save()
                                except OrderSplitItem.DoesNotExist:
                                    # Wenn nicht, neues Split-Item erstellen
                                    if quantity > 0:
                                        OrderSplitItem.objects.create(
                                            order_split=split,
                                            order_item=item,
                                            quantity=quantity
                                        )

                            items_received = True

                # Wenn keine Artikel empfangen wurden, Wareneingang löschen
                if not items_received:
                    if split and create_split:
                        split.delete()
                    receipt.delete()
                    messages.warning(request, 'Es wurden keine Artikel als empfangen markiert.')
                    return redirect('purchase_order_detail', pk=order.pk)

                # Bestellstatus aktualisieren
                update_order_status(order)

                # Automatisch eine neue Teillieferung für ausstehende Artikel anlegen, wenn gewünscht
                create_future_split = request.POST.get('create_future_split') == 'yes' and is_partial_receipt
                if create_future_split:
                    future_split_name = request.POST.get('future_split_name', '')
                    future_delivery_date = request.POST.get('future_delivery_date', None)

                    future_split = OrderSplit.objects.create(
                        purchase_order=order,
                        name=future_split_name or "Restlieferung",
                        expected_delivery=future_delivery_date,
                        status='planned',
                        created_by=request.user
                    )

                    # Für jede Position die ausstehende Menge in die neue Teillieferung aufnehmen
                    for item in items:
                        remaining = item.quantity_ordered - item.quantity_received
                        if remaining > 0:
                            OrderSplitItem.objects.create(
                                order_split=future_split,
                                order_item=item,
                                quantity=remaining
                            )

                    messages.success(request,
                                     f'Wareneingang wurde erfasst und eine neue geplante Teillieferung "{future_split.name}" wurde angelegt.')
                else:
                    if use_existing_split and split:
                        messages.success(request,
                                         f'Wareneingang für Teillieferung "{split.name}" wurde erfolgreich erfasst.')
                    else:
                        messages.success(request, 'Wareneingang wurde erfolgreich erfasst.')

                # Wenn defekte Artikel gemeldet wurden, in der Session speichern und zur RMA-Erstellung weiterleiten
                if defective_items:
                    # Defekte Artikel mit Wareneingangspositionen verknüpfen
                    for item_data in defective_items:
                        item_id = item_data.get('receipt_item_id')
                        # Suche die entsprechende ReceiptItem für diese Position
                        for ri in receipt.items.all():
                            if str(ri.order_item.id) == str(item_id):
                                item_data['receipt_item_id'] = ri.id
                                break

                    # In Session speichern
                    request.session['defective_items'] = defective_items

                    # Prüfen, ob mindestens ein Artikel für RMA markiert ist
                    create_rma = any(item.get('create_rma', False) for item in defective_items)
                    if create_rma:
                        messages.info(request,
                                      'Es wurden mangelhafte Artikel erfasst. Sie werden zur RMA-Erstellung weitergeleitet.')
                        return redirect('rma_create_from_receipt', order_id=order.pk, receipt_id=receipt.pk)

                return redirect('purchase_order_detail', pk=order.pk)

        except Exception as e:
            messages.error(request, f'Fehler beim Speichern des Wareneingangs: {str(e)}')

    # Vorbereiten des Kontexts für die Template-Rendering
    context = {
        'order': order,
        'items': items,
        'warehouses': warehouses,
        'has_batch_products': has_batch_products,
        'has_expiry_products': has_expiry_products,
    }

    return render(request, 'order/purchase_order_receive_unified.html', context)

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
    """Export einer Bestellung als CSV oder PDF mit Berücksichtigung stornierter Mengen."""
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

        # Daten - verwende display_quantity und überspringe stornierte Positionen
        for item in order.items.all():
            # Vollständig stornierte Positionen überspringen
            if item.is_canceled:
                continue

            writer.writerow([
                order.order_number,
                order.supplier.name,
                order.order_date.strftime('%d.%m.%Y'),
                order.get_status_display(),
                item.product.name,
                item.supplier_sku,
                item.display_quantity,  # Statt quantity_ordered
                item.product.unit,
                item.unit_price,
                item.display_line_total  # Statt line_total
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

    # Get reference to the associated split before anything else
    associated_split = receipt.order_split
    delete_split = False  # Default: Do not delete the split

    if request.method == 'POST':
        # Check if user wants to delete the split too
        delete_split = request.POST.get('delete_split') == 'yes'

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

            # Delete the receipt first
            receipt.delete()

            # Handle the associated split if it exists
            if associated_split:
                # Check if there are any remaining receipts for this split
                remaining_receipts = PurchaseOrderReceipt.objects.filter(order_split=associated_split).exists()

                if not remaining_receipts:
                    if delete_split:
                        # User has chosen to delete the split as well since it has no more receipts
                        split_name = associated_split.name
                        associated_split.delete()
                        messages.info(request, f'Teillieferung "{split_name}" wurde vollständig gelöscht.')
                    else:
                        # Just reset the status to 'planned'
                        associated_split.status = 'planned'
                        associated_split.save()
                        messages.info(request,
                                      f'Teillieferung "{associated_split.name}" wurde zurück auf "Geplant" gesetzt.')

            # Update order status using the helper function
            update_order_status_after_receipt(order)

            messages.success(request, f'Wareneingang für Bestellung {order.order_number} wurde erfolgreich gelöscht.')

        return redirect('purchase_order_detail', pk=order.pk)

    # Check if this is the only receipt for its split
    is_only_receipt = False
    if associated_split:
        is_only_receipt = PurchaseOrderReceipt.objects.filter(order_split=associated_split).count() == 1

    context = {
        'order': order,
        'receipt': receipt,
        'associated_split': associated_split,
        'is_only_receipt': is_only_receipt,
    }

    return render(request, 'order/purchase_order_receipt_confirm_delete.html', context)


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


@login_required
@permission_required('order', 'view')
def order_template_list(request):
    """List all order templates with filtering options."""
    # Base queryset
    queryset = OrderTemplate.objects.select_related('supplier', 'created_by')

    # Apply filters
    supplier = request.GET.get('supplier', '')
    is_recurring = request.GET.get('is_recurring', '')
    search = request.GET.get('search', '')

    if supplier:
        queryset = queryset.filter(supplier_id=supplier)

    if is_recurring:
        is_recurring_bool = is_recurring.lower() == 'true'
        queryset = queryset.filter(is_recurring=is_recurring_bool)

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(supplier__name__icontains=search)
        )

    # Order by name
    queryset = queryset.order_by('name')

    # Pagination
    paginator = Paginator(queryset, 10)  # 10 templates per page
    page = request.GET.get('page')
    try:
        templates = paginator.page(page)
        # Calculate page range
        page_range = range(max(1, templates.number - 2), min(paginator.num_pages + 1, templates.number + 3))
    except PageNotAnInteger:
        templates = paginator.page(1)
        page_range = range(1, min(paginator.num_pages + 1, 6))
    except EmptyPage:
        templates = paginator.page(paginator.num_pages)
        page_range = range(max(1, paginator.num_pages - 4), paginator.num_pages + 1)

    # Suppliers for filter dropdown
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')

    context = {
        'templates': templates,
        'page_range': page_range,
        'suppliers': suppliers,
        'supplier': supplier,
        'is_recurring': is_recurring,
        'search': search,
    }

    return render(request, 'order/order_template_list.html', context)


@login_required
@permission_required('order', 'view')
def order_template_detail(request, pk):
    """Show details for a specific order template."""
    template = get_object_or_404(
        OrderTemplate.objects.select_related('supplier', 'created_by'),
        pk=pk
    )

    # Calculate current prices and estimated values for items
    items = template.items.all().select_related('product')

    # System currency
    system_currency = Currency.get_default_currency()
    currency_symbol = system_currency.symbol if system_currency else '€'

    total_value = Decimal('0.00')

    for item in items:
        # Try to get current supplier price
        try:
            supplier_product = SupplierProduct.objects.get(
                supplier=template.supplier,
                product=item.product
            )
            item.current_price = supplier_product.purchase_price
            item.estimated_value = item.current_price * item.quantity
            total_value += item.estimated_value
        except SupplierProduct.DoesNotExist:
            item.current_price = None
            item.estimated_value = None

    # Get orders created from this template
    orders = PurchaseOrder.objects.filter(
        template_source=template
    ).order_by('-order_date')[:10]  # Only show the last 10 orders

    context = {
        'template': template,
        'items': items,
        'total_value': total_value,
        'currency_symbol': currency_symbol,
        'orders': orders,
    }

    return render(request, 'order/order_template_detail.html', context)


@login_required
@permission_required('order', 'create')
def order_template_create(request):
    """Create a new order template."""
    if request.method == 'POST':
        name = request.POST.get('name')
        supplier_id = request.POST.get('supplier')
        description = request.POST.get('description', '')
        is_active = 'is_active' in request.POST
        is_recurring = 'is_recurring' in request.POST
        recurrence_frequency = request.POST.get('recurrence_frequency', 'none')
        next_order_date = request.POST.get('next_order_date', None)
        shipping_address = request.POST.get('shipping_address', '')
        notes = request.POST.get('notes', '')

        if not name or not supplier_id:
            messages.error(request, 'Vorlagenname und Lieferant sind erforderlich.')
            return redirect('order_template_create')

        try:
            supplier = Supplier.objects.get(pk=supplier_id)
        except Supplier.DoesNotExist:
            messages.error(request, 'Der ausgewählte Lieferant existiert nicht.')
            return redirect('order_template_create')

        # Create template
        with transaction.atomic():
            template = OrderTemplate.objects.create(
                name=name,
                supplier=supplier,
                description=description,
                is_active=is_active,
                is_recurring=is_recurring,
                recurrence_frequency=recurrence_frequency,
                next_order_date=next_order_date if next_order_date else None,
                shipping_address=shipping_address,
                notes=notes,
                created_by=request.user
            )

            # Process items
            process_template_items(request.POST, template)

            messages.success(request, f'Bestellvorlage "{template.name}" wurde erfolgreich erstellt.')
            return redirect('order_template_detail', pk=template.pk)

    # For GET requests
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    recurrence_choices = OrderTemplate.RECURRENCE_CHOICES

    context = {
        'suppliers': suppliers,
        'recurrence_choices': recurrence_choices,
    }

    return render(request, 'order/order_template_form.html', context)


@login_required
@permission_required('order', 'edit')
def order_template_update(request, pk):
    """Update an existing order template."""
    template = get_object_or_404(OrderTemplate, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name')
        supplier_id = request.POST.get('supplier')
        description = request.POST.get('description', '')
        is_active = 'is_active' in request.POST
        is_recurring = 'is_recurring' in request.POST
        recurrence_frequency = request.POST.get('recurrence_frequency', 'none')
        next_order_date = request.POST.get('next_order_date', None)
        shipping_address = request.POST.get('shipping_address', '')
        notes = request.POST.get('notes', '')

        # Debug logging for troubleshooting
        print(f"Name: '{name}', Supplier ID: '{supplier_id}'")

        if not name or not supplier_id:
            messages.error(request, 'Vorlagenname und Lieferant sind erforderlich.')
            # Instead of redirecting, render the form with existing data
            suppliers = Supplier.objects.filter(is_active=True).order_by('name')
            recurrence_choices = OrderTemplate.RECURRENCE_CHOICES
            context = {
                'form': {'instance': template},  # Mock form for template compatibility
                'template': template,
                'suppliers': suppliers,
                'recurrence_choices': recurrence_choices,
            }
            return render(request, 'order/order_template_form.html', context)

        try:
            supplier = Supplier.objects.get(pk=supplier_id)
        except Supplier.DoesNotExist:
            messages.error(request, 'Der ausgewählte Lieferant existiert nicht.')
            # Instead of redirecting, render the form with existing data
            suppliers = Supplier.objects.filter(is_active=True).order_by('name')
            recurrence_choices = OrderTemplate.RECURRENCE_CHOICES
            context = {
                'form': {'instance': template},  # Mock form for template compatibility
                'template': template,
                'suppliers': suppliers,
                'recurrence_choices': recurrence_choices,
            }
            return render(request, 'order/order_template_form.html', context)

        # Update template
        with transaction.atomic():
            template.name = name
            template.supplier = supplier
            template.description = description
            template.is_active = is_active
            template.is_recurring = is_recurring
            template.recurrence_frequency = recurrence_frequency
            template.next_order_date = next_order_date if next_order_date else None
            template.shipping_address = shipping_address
            template.notes = notes
            template.save()

            # Process items
            process_template_items(request.POST, template)

            messages.success(request, f'Bestellvorlage "{template.name}" wurde erfolgreich aktualisiert.')
            return redirect('order_template_detail', pk=template.pk)

    # For GET requests
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    recurrence_choices = OrderTemplate.RECURRENCE_CHOICES

    context = {
        'form': {'instance': template},  # Mock form for template compatibility
        'template': template,
        'suppliers': suppliers,
        'recurrence_choices': recurrence_choices,
    }

    return render(request, 'order/order_template_form.html', context)


def process_template_items(post_data, template):
    """Process template items from form data."""
    # Print debugging information
    print(f"Processing items for template: {template.id} - {template.name}")

    # Get existing items
    existing_items = {item.id: item for item in template.items.all()}
    processed_ids = set()

    # Process items
    for key in post_data.keys():
        # Check if it's a product field
        if key.startswith('item_product_'):
            # Extract item ID (new_X or a number)
            item_id = key.split('item_product_')[1]

            # Get product ID
            product_id = post_data[key]
            if not product_id:
                print(f"No product ID for key: {key}")
                continue

            print(f"Processing item_id: {item_id}, product_id: {product_id}")

            # Find corresponding quantity and supplier_sku
            quantity_key = f'item_quantity_{item_id}'
            supplier_sku_key = f'item_supplier_sku_{item_id}'

            if quantity_key in post_data:
                try:
                    quantity = Decimal(post_data[quantity_key])
                    supplier_sku = post_data.get(supplier_sku_key, '')

                    print(f"Quantity: {quantity}, Supplier SKU: {supplier_sku}")

                    # Get product
                    try:
                        product = Product.objects.get(pk=product_id)
                        print(f"Found product: {product.name}")

                        if item_id.startswith('new_'):
                            # Create new item
                            OrderTemplateItem.objects.create(
                                template=template,
                                product=product,
                                quantity=quantity,
                                supplier_sku=supplier_sku
                            )
                            print(f"Created new item for product: {product.name}")
                        else:
                            # Update existing item
                            try:
                                item_id_int = int(item_id)
                                if item_id_int in existing_items:
                                    item = existing_items[item_id_int]
                                    item.product = product
                                    item.quantity = quantity
                                    item.supplier_sku = supplier_sku
                                    item.save()
                                    processed_ids.add(item_id_int)
                                    print(f"Updated existing item: {item_id_int}")
                                else:
                                    print(f"Item ID not found in existing items: {item_id_int}")
                            except (ValueError, KeyError) as e:
                                print(f"Error processing existing item {item_id}: {str(e)}")
                                continue
                    except Product.DoesNotExist:
                        print(f"Product not found with ID: {product_id}")
                        continue
                except (ValueError, TypeError) as e:
                    print(f"Error with quantity for {item_id}: {str(e)}")
                    continue
            else:
                print(f"Quantity key not found: {quantity_key}")

    # Delete items that weren't processed
    for item_id, item in existing_items.items():
        if item_id not in processed_ids:
            print(f"Deleting item: {item_id}")
            item.delete()

    # Print summary
    print(f"Processed {len(processed_ids)} existing items")
    print(f"Existing items: {len(existing_items)}")


@login_required
@permission_required('order', 'delete')
def order_template_delete(request, pk):
    """Delete an order template."""
    template = get_object_or_404(OrderTemplate, pk=pk)

    if request.method == 'POST':
        template_name = template.name
        template.delete()
        messages.success(request, f'Bestellvorlage "{template_name}" wurde erfolgreich gelöscht.')
        return redirect('order_template_list')

    context = {
        'template': template,
    }

    return render(request, 'order/order_template_delete.html', context)


@login_required
@permission_required('order', 'edit')
def order_template_toggle_active(request, pk):
    """Toggle active status of an order template."""
    template = get_object_or_404(OrderTemplate, pk=pk)

    # Get desired state from request
    is_active = request.GET.get('active', '').lower() == 'true'

    template.is_active = is_active
    template.save(update_fields=['is_active'])

    if is_active:
        messages.success(request, f'Bestellvorlage "{template.name}" wurde aktiviert.')
    else:
        messages.success(request, f'Bestellvorlage "{template.name}" wurde deaktiviert.')

    return redirect('order_template_detail', pk=template.pk)


@login_required
@permission_required('order', 'create')
def order_template_duplicate(request, pk):
    """Duplicate an order template."""
    template = get_object_or_404(OrderTemplate, pk=pk)

    # Create a new template with the same data
    new_template = OrderTemplate.objects.create(
        name=f"{template.name} (Kopie)",
        supplier=template.supplier,
        description=template.description,
        is_active=template.is_active,
        is_recurring=False,  # Don't duplicate recurrence settings
        recurrence_frequency='none',
        next_order_date=None,
        shipping_address=template.shipping_address,
        notes=template.notes,
        created_by=request.user
    )

    # Duplicate items
    for item in template.items.all():
        OrderTemplateItem.objects.create(
            template=new_template,
            product=item.product,
            quantity=item.quantity,
            supplier_sku=item.supplier_sku
        )

    messages.success(request, f'Bestellvorlage "{template.name}" wurde als "{new_template.name}" dupliziert.')
    return redirect('order_template_detail', pk=new_template.pk)


@login_required
@permission_required('order', 'create')
def create_order_from_template(request, pk):
    """Create a purchase order from a template."""
    template = get_object_or_404(
        OrderTemplate.objects.select_related('supplier').prefetch_related('items__product'),
        pk=pk
    )

    # Check if the template has items
    if not template.items.exists():
        messages.error(request, f'Die Vorlage "{template.name}" enthält keine Artikelpositionen.')
        return redirect('order_template_detail', pk=template.pk)

    # Process the request
    if request.method == 'POST':
        # Get expected delivery date from the form, if provided
        expected_delivery = request.POST.get('expected_delivery', None)
        notes = request.POST.get('notes', template.notes)

        with transaction.atomic():
            # Generate order number
            today = date.today()

            # Try to get system settings for order number prefix
            try:
                from admin_dashboard.models import SystemSettings
                system_settings = SystemSettings.objects.first()
                prefix = system_settings.order_number_prefix if system_settings else "ORD-"
                next_seq = system_settings.next_order_number if system_settings else 1
            except:
                # Fallback if no system settings
                prefix = "ORD-"
                next_seq = 1

            order_number_prefix = f"{prefix}{today.strftime('%Y%m%d')}-"

            # Find next sequence number
            last_order = PurchaseOrder.objects.filter(
                order_number__startswith=order_number_prefix
            ).order_by('-order_number').first()

            if last_order:
                try:
                    last_seq = int(last_order.order_number.split('-')[-1])
                    next_seq = last_seq + 1
                except ValueError:
                    pass  # Use the default next_seq

            order_number = f"{order_number_prefix}{next_seq:03d}"

            # Create the order
            order = PurchaseOrder.objects.create(
                order_number=order_number,
                supplier=template.supplier,
                status=get_initial_order_status(None),  # Determine initial status
                expected_delivery=expected_delivery if expected_delivery else None,
                shipping_address=template.shipping_address,
                notes=notes,
                created_by=request.user,
                template_source=template  # Reference to the source template
            )

            # Create order items
            for template_item in template.items.all():
                # Try to get the current price from supplier products
                try:
                    supplier_product = SupplierProduct.objects.get(
                        supplier=template.supplier,
                        product=template_item.product
                    )
                    unit_price = supplier_product.purchase_price
                    supplier_sku = supplier_product.supplier_sku
                    # Add currency if available
                    currency = supplier_product.currency or template.supplier.default_currency
                except SupplierProduct.DoesNotExist:
                    # Use a default price if no supplier product exists
                    unit_price = Decimal('0.00')
                    supplier_sku = template_item.supplier_sku
                    currency = None

                # Create the order item
                PurchaseOrderItem.objects.create(
                    purchase_order=order,
                    product=template_item.product,
                    quantity_ordered=template_item.quantity,
                    unit_price=unit_price,
                    supplier_sku=supplier_sku,
                    tax=template_item.product.tax,
                    currency=currency
                )

            # Update totals
            order.update_totals()

            # Update system settings if they exist
            if 'system_settings' in locals() and system_settings:
                system_settings.next_order_number = next_seq + 1
                system_settings.save()

            messages.success(request,
                             f'Bestellung {order.order_number} wurde erfolgreich aus der Vorlage "{template.name}" erstellt.')
            return redirect('purchase_order_detail', pk=order.pk)

    # For GET requests, just redirect to template detail with showing modal via URL parameter
    return redirect(f"{reverse('order_template_detail', kwargs={'pk': template.pk})}?show_modal=true")


@login_required
def handle_recurring_orders():
    """
    Process recurring order templates and create new orders.
    This function is meant to be called by a scheduled job.
    """
    today = date.today()

    # Find active templates with recurrence and next_order_date <= today
    templates = OrderTemplate.objects.filter(
        is_active=True,
        is_recurring=True,
        next_order_date__lte=today
    ).select_related('supplier').prefetch_related('items__product')

    orders_created = 0

    for template in templates:
        with transaction.atomic():
            try:
                # Skip templates without items
                if not template.items.exists():
                    continue

                # Calculate next order date based on recurrence frequency
                if template.recurrence_frequency == 'daily':
                    next_date = today + timedelta(days=1)
                elif template.recurrence_frequency == 'weekly':
                    next_date = today + timedelta(weeks=1)
                elif template.recurrence_frequency == 'biweekly':
                    next_date = today + timedelta(weeks=2)
                elif template.recurrence_frequency == 'monthly':
                    # Add a month (approximate)
                    next_date = date(today.year + ((today.month + 1) // 12), ((today.month + 1) % 12) or 12,
                                     min(today.day, 28))
                elif template.recurrence_frequency == 'quarterly':
                    # Add 3 months (approximate)
                    next_date = date(today.year + ((today.month + 3) // 12), ((today.month + 3) % 12) or 12,
                                     min(today.day, 28))
                elif template.recurrence_frequency == 'semiannual':
                    # Add 6 months (approximate)
                    next_date = date(today.year + ((today.month + 6) // 12), ((today.month + 6) % 12) or 12,
                                     min(today.day, 28))
                elif template.recurrence_frequency == 'annual':
                    # Add a year
                    next_year = today.year + 1
                    next_date = date(next_year, today.month, min(today.day, 28 if today.month == 2 and (
                                next_year % 4 != 0 or (next_year % 100 == 0 and next_year % 400 != 0)) else (
                        29 if today.month == 2 else (30 if today.month in [4, 6, 9, 11] else 31))))
                else:
                    # Default: no recurrence
                    next_date = None

                # Generate order number
                try:
                    from admin_dashboard.models import SystemSettings
                    system_settings = SystemSettings.objects.first()
                    prefix = system_settings.order_number_prefix if system_settings else "ORD-"
                    next_seq = system_settings.next_order_number if system_settings else 1
                except:
                    # Fallback
                    prefix = "ORD-"
                    next_seq = 1

                order_number_prefix = f"{prefix}{today.strftime('%Y%m%d')}-"

                # Find next sequence number
                last_order = PurchaseOrder.objects.filter(
                    order_number__startswith=order_number_prefix
                ).order_by('-order_number').first()

                if last_order:
                    try:
                        last_seq = int(last_order.order_number.split('-')[-1])
                        next_seq = last_seq + 1
                    except ValueError:
                        pass

                order_number = f"{order_number_prefix}{next_seq:03d}"

                # Create order
                order = PurchaseOrder.objects.create(
                    order_number=order_number,
                    supplier=template.supplier,
                    status='draft',  # Always start as draft for recurring orders
                    shipping_address=template.shipping_address,
                    notes=f"Automatisch erstellt aus Vorlage: {template.name}",
                    created_by=template.created_by,
                    template_source=template
                )

                # Create order items
                for template_item in template.items.all():
                    try:
                        supplier_product = SupplierProduct.objects.get(
                            supplier=template.supplier,
                            product=template_item.product
                        )
                        unit_price = supplier_product.purchase_price
                        supplier_sku = supplier_product.supplier_sku
                        currency = supplier_product.currency or template.supplier.default_currency
                    except SupplierProduct.DoesNotExist:
                        unit_price = Decimal('0.00')
                        supplier_sku = template_item.supplier_sku
                        currency = None

                    PurchaseOrderItem.objects.create(
                        purchase_order=order,
                        product=template_item.product,
                        quantity_ordered=template_item.quantity,
                        unit_price=unit_price,
                        supplier_sku=supplier_sku,
                        tax=template_item.product.tax,
                        currency=currency
                    )

                # Update totals
                order.update_totals()

                # Update template's next order date
                template.next_order_date = next_date
                template.save(update_fields=['next_order_date'])

                # Update system settings if they exist
                if 'system_settings' in locals() and system_settings:
                    system_settings.next_order_number = next_seq + 1
                    system_settings.save()

                orders_created += 1

            except Exception as e:
                # Log error but continue with other templates
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error creating recurring order from template {template.id}: {str(e)}")

    return orders_created


@login_required
@permission_required('order', 'edit')
def purchase_order_item_cancel(request, pk, item_id):
    """Cancel a specific order item."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    item = get_object_or_404(PurchaseOrderItem, pk=item_id, purchase_order=order)

    # Prüfen, ob die Bestellung bereits bestellt oder weiter ist
    # Ein strikter Check, der alle Statuswerte prüft, die "bestellt" oder später sind
    if order.status in ['sent', 'partially_received', 'received', 'canceled']:
        messages.error(request,
                       f'Bestellposition kann nicht storniert werden, da die Bestellung bereits den Status "{order.get_status_display()}" hat und an den Lieferanten übermittelt wurde.')
        return redirect('purchase_order_detail', pk=order.pk)

    # Check if the order is in a state where cancellation is allowed
    if order.status in ['received', 'canceled']:
        messages.error(request,
                       f'Bestellposition kann nicht storniert werden, da die Bestellung bereits {order.get_status_display()} ist.')
        return redirect('purchase_order_detail', pk=order.pk)

    # Check if the item is already received
    if item.quantity_received > 0:
        messages.error(request,
                       'Bestellposition kann nicht storniert werden, da bereits Ware eingegangen ist.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        # Get cancellation parameters
        cancel_type = request.POST.get('cancel_type', 'full')
        cancel_quantity = None

        if cancel_type == 'partial':
            try:
                cancel_quantity = Decimal(request.POST.get('cancel_quantity', '0'))
                if cancel_quantity <= 0 or cancel_quantity > item.quantity_ordered:
                    raise ValueError("Invalid cancellation quantity")
            except (ValueError, InvalidOperation):
                messages.error(request, 'Ungültige Stornierungsmenge angegeben.')
                return redirect('purchase_order_item_cancel', pk=order.pk, item_id=item.id)

        reason = request.POST.get('reason', '')

        try:
            # Cancel the item
            item.cancel(request.user, cancel_quantity, reason)

            # Success message
            if cancel_quantity:
                messages.success(request,
                                 f'Bestellposition für {item.product.name} wurde teilweise storniert ({cancel_quantity} {item.product.unit}).')
            else:
                messages.success(request,
                                 f'Bestellposition für {item.product.name} wurde vollständig storniert.')

            # Recalculate order totals to reflect the cancellation
            order.update_totals()

            return redirect('purchase_order_detail', pk=order.pk)
        except ValueError as e:
            messages.error(request, f'Fehler bei der Stornierung: {str(e)}')
            return redirect('purchase_order_detail', pk=order.pk)

    # For GET request, show the cancellation form
    context = {
        'order': order,
        'item': item,
    }

    return render(request, 'order/purchase_order_item_cancel.html', context)


@login_required
@permission_required('order', 'edit')
def purchase_order_item_edit_cancellation(request, pk, item_id):
    """Stornierung einer Bestellposition bearbeiten oder rückgängig machen."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    item = get_object_or_404(PurchaseOrderItem, pk=item_id, purchase_order=order)

    # Prüfen, ob Position storniert ist
    if item.status not in ['canceled', 'partially_canceled']:
        messages.error(request, 'Nur stornierte Positionen können bearbeitet werden.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        # Aktion bestimmen
        action = request.POST.get('action', '')

        try:
            if action == 'edit':
                # Neue Stornierungsmenge und Grund
                try:
                    new_quantity = Decimal(request.POST.get('cancel_quantity', '0'))
                except (ValueError, InvalidOperation):
                    messages.error(request, 'Ungültige Stornierungsmenge angegeben.')
                    return redirect('purchase_order_item_edit_cancellation', pk=order.pk, item_id=item.id)

                new_reason = request.POST.get('reason', '')

                # Stornierung bearbeiten
                item.edit_cancellation(request.user, new_quantity, new_reason)

                messages.success(request, f'Stornierung für {item.product.name} wurde aktualisiert.')

            elif action == 'revert':
                # Stornierung vollständig rückgängig machen
                item.edit_cancellation(request.user, 0, '')

                messages.success(request, f'Stornierung für {item.product.name} wurde rückgängig gemacht.')

            else:
                messages.error(request, 'Ungültige Aktion.')

            # Summen der Bestellung aktualisieren
            order.update_totals()

            return redirect('purchase_order_detail', pk=order.pk)

        except ValueError as e:
            messages.error(request, f'Fehler: {str(e)}')

    # Vorbereitung der Formularansicht
    context = {
        'order': order,
        'item': item,
        'original_quantity': item.original_quantity,
        'canceled_quantity': item.canceled_quantity,
        'effective_quantity': item.effective_quantity,
    }

    return render(request, 'order/purchase_order_item_edit_cancellation.html', context)


@login_required
@permission_required('order', 'edit')
def order_split_create(request, pk):
    """Create a new order split (partial shipment) for a purchase order."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Only orders in 'sent' or 'partially_received' status can be split
    if order.status not in ['sent', 'partially_received']:
        messages.error(request,
                       f'Teillieferungen können nur für Bestellungen im Status "Bestellt" oder "Teilweise erhalten" erstellt werden.')
        return redirect('purchase_order_detail', pk=order.pk)

    # Get all items that can be split (not fully received, not canceled)
    items = order.items.filter(
        quantity_received__lt=models.F('quantity_ordered'),
        status__in=['active', 'partially_canceled']
    )

    if not items.exists():
        messages.error(request, 'Es gibt keine Positionen, die für eine Teillieferung verfügbar sind.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        form = OrderSplitForm(request.POST)
        formset = OrderSplitItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                # Create the order split
                order_split = form.save(commit=False)
                order_split.purchase_order = order
                order_split.created_by = request.user
                order_split.save()

                # Process the items
                any_items_added = False
                for form_item in formset:
                    if form_item.cleaned_data and form_item.cleaned_data.get('split_quantity'):
                        item_id = form_item.cleaned_data['item_id']
                        quantity = form_item.cleaned_data['split_quantity']

                        if quantity > 0:
                            # Get the order item
                            try:
                                order_item = order.items.get(pk=item_id)

                                # Create the split item
                                OrderSplitItem.objects.create(
                                    order_split=order_split,
                                    order_item=order_item,
                                    quantity=quantity
                                )

                                any_items_added = True
                            except PurchaseOrderItem.DoesNotExist:
                                # Skip if the item doesn't exist
                                pass

                if not any_items_added:
                    # If no items were added, delete the split and show error
                    order_split.delete()
                    messages.error(request, 'Die Teillieferung wurde nicht erstellt, da keine Mengen angegeben wurden.')
                    return redirect('order_split_create', pk=order.pk)

                messages.success(request, f'Teillieferung "{order_split.name}" wurde erfolgreich erstellt.')
                return redirect('purchase_order_detail', pk=order.pk)
    else:
        form = OrderSplitForm()

        # Prepare initial data for the formset
        initial_data = []
        for item in items:
            # Calculate remaining quantity (ordered - received - already in other splits)
            already_split_quantity = OrderSplitItem.objects.filter(
                order_item=item
            ).aggregate(total=models.Sum('quantity'))['total'] or Decimal('0')

            effective_quantity = item.effective_quantity  # This accounts for cancellations
            remaining = effective_quantity - item.quantity_received - already_split_quantity

            if remaining > 0:
                initial_data.append({
                    'item_id': item.id,
                    'product_name': item.product.name,
                    'product_sku': item.product.sku,
                    'total_quantity': effective_quantity,
                    'remaining_quantity': remaining,
                    'unit': item.product.unit,
                    'split_quantity': Decimal('0')
                })

        formset = OrderSplitItemFormSet(initial=initial_data)

    context = {
        'order': order,
        'form': form,
        'formset': formset,
    }

    return render(request, 'order/order_split_form.html', context)


@login_required
@permission_required('order', 'view')
def order_split_list(request, pk):
    """List all splits for a purchase order."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    splits = order.splits.all().order_by('expected_delivery')

    context = {
        'order': order,
        'splits': splits,
    }

    return render(request, 'order/order_split_list.html', context)


@login_required
@permission_required('order', 'view')
def order_split_detail(request, pk, split_id):
    """Show details for a specific order split."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    split = get_object_or_404(OrderSplit, pk=split_id, purchase_order=order)

    # Get related receipts
    receipts = split.receipts.all()

    context = {
        'order': order,
        'split': split,
        'receipts': receipts,
    }

    return render(request, 'order/order_split_detail.html', context)


@login_required
@permission_required('order', 'edit')
def order_split_update(request, pk, split_id):
    """Update an existing order split."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    split = get_object_or_404(OrderSplit, pk=split_id, purchase_order=order)

    # Only allow updates if split is planned (not received yet)
    if split.status != 'planned':
        messages.error(request, 'Nur geplante Teillieferungen können bearbeitet werden.')
        return redirect('order_split_detail', pk=order.pk, split_id=split.pk)

    if request.method == 'POST':
        form = OrderSplitForm(request.POST, instance=split)

        if form.is_valid():
            form.save()
            messages.success(request, f'Teillieferung "{split.name}" wurde erfolgreich aktualisiert.')
            return redirect('order_split_detail', pk=order.pk, split_id=split.pk)
    else:
        form = OrderSplitForm(instance=split)

    context = {
        'order': order,
        'split': split,
        'form': form,
    }

    return render(request, 'order/order_split_edit.html', context)


@login_required
@permission_required('order', 'edit')
def order_split_delete(request, pk, split_id):
    """Delete an order split."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    split = get_object_or_404(OrderSplit, pk=split_id, purchase_order=order)

    # Only allow deletion if split has no receipts
    if split.receipts.exists():
        messages.error(request,
                       'Diese Teillieferung kann nicht gelöscht werden, da bereits Wareneingänge erfasst wurden.')
        return redirect('order_split_detail', pk=order.pk, split_id=split.pk)

    if request.method == 'POST':
        split_name = split.name
        split.delete()
        messages.success(request, f'Teillieferung "{split_name}" wurde erfolgreich gelöscht.')
        return redirect('order_split_list', pk=order.pk)

    context = {
        'order': order,
        'split': split,
    }

    return render(request, 'order/order_split_confirm_delete.html', context)


@login_required
@permission_required('order', 'receive')
def receive_order_split(request, pk, split_id):
    """Receive goods for a specific order split."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    split = get_object_or_404(OrderSplit, pk=split_id, purchase_order=order)

    # Only planned or in_transit splits can be received
    if split.status not in ['planned', 'in_transit']:
        messages.error(request, 'Nur geplante oder unterwegs befindliche Teillieferungen können empfangen werden.')
        return redirect('order_split_detail', pk=order.pk, split_id=split.pk)

    # Get available warehouses
    warehouses = Warehouse.objects.filter(is_active=True)

    # Check if any items in the split require batch or expiry tracking
    has_batch_products = any(item.order_item.product.has_batch_tracking for item in split.items.all())
    has_expiry_products = any(item.order_item.product.has_expiry_tracking for item in split.items.all())

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Create receipt and link it to the split
                receipt = PurchaseOrderReceipt.objects.create(
                    purchase_order=order,
                    received_by=request.user,
                    notes=request.POST.get('notes', ''),
                    order_split=split  # Link to the split
                )

                # Process items from the split
                items_received = False

                for split_item in split.items.all():
                    # Get the quantity received for this item
                    quantity_key = f'receive_quantity_{split_item.id}'
                    warehouse_key = f'warehouse_{split_item.id}'
                    batch_key = f'batch_{split_item.id}'
                    expiry_key = f'expiry_{split_item.id}'

                    if quantity_key in request.POST:
                        try:
                            quantity = Decimal(request.POST[quantity_key])
                        except (ValueError, InvalidOperation):
                            quantity = Decimal('0')

                        if quantity > 0:
                            # Get the warehouse
                            warehouse_id = request.POST.get(warehouse_key)
                            if not warehouse_id:
                                raise ValueError(
                                    f"Kein Lager für Artikel {split_item.order_item.product.name} angegeben")

                            warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

                            # Get batch and expiry info if needed
                            batch_number = request.POST.get(batch_key, '')
                            expiry_date = None

                            if expiry_key in request.POST and request.POST.get(expiry_key):
                                try:
                                    expiry_date = date.fromisoformat(request.POST.get(expiry_key))
                                except ValueError:
                                    # Invalid date format, leave as None
                                    pass

                            # Create receipt item
                            receipt_item = PurchaseOrderReceiptItem.objects.create(
                                receipt=receipt,
                                order_item=split_item.order_item,
                                quantity_received=quantity,
                                warehouse=warehouse,
                                batch_number=batch_number,
                                expiry_date=expiry_date
                            )

                            # Create or update batch if tracking is enabled
                            if batch_number and split_item.order_item.product.has_batch_tracking:
                                from core.models import BatchNumber
                                # Create or update the batch
                                batch_obj, created = BatchNumber.objects.update_or_create(
                                    product=split_item.order_item.product,
                                    batch_number=batch_number,
                                    warehouse=warehouse,
                                    defaults={
                                        'quantity': quantity,
                                        'expiry_date': expiry_date,
                                        'supplier': order.supplier,
                                        'notes': f'Batch aus Wareneingang: {order.order_number} - {split.name}'
                                    }
                                )

                                if not created:
                                    # If batch already exists, increase quantity
                                    batch_obj.quantity += quantity
                                    batch_obj.save()

                            # Create stock movement
                            StockMovement.objects.create(
                                product=split_item.order_item.product,
                                warehouse=warehouse,
                                quantity=quantity,
                                movement_type='in',
                                reference=f'Wareneingang: {order.order_number} - {split.name}',
                                notes=f'Empfangene Menge: {quantity}, Charge: {batch_number}',
                                created_by=request.user
                            )

                            # Update product warehouse quantity
                            product_warehouse, created = ProductWarehouse.objects.get_or_create(
                                product=split_item.order_item.product,
                                warehouse=warehouse,
                                defaults={'quantity': 0}
                            )

                            product_warehouse.quantity += quantity
                            product_warehouse.save()

                            # Update the order item's received quantity
                            split_item.order_item.quantity_received += quantity
                            split_item.order_item.save()

                            items_received = True

                # Update split status if items were received
                if items_received:
                    # Check if all items in the split have been fully received
                    all_items_received = True
                    for split_item in split.items.all():
                        order_item = split_item.order_item

                        # Calculate total received for this item (possibly from multiple receipts)
                        total_received_for_item = PurchaseOrderReceiptItem.objects.filter(
                            order_item=order_item
                        ).aggregate(Sum('quantity_received'))['quantity_received__sum'] or 0

                        if total_received_for_item < split_item.quantity:
                            all_items_received = False
                            break

                    if all_items_received:
                        split.status = 'received'
                        split.save()

                    # Update order status
                    update_order_status_after_receipt(order)

                    messages.success(request,
                                     f'Wareneingang für Teillieferung "{split.name}" wurde erfolgreich erfasst.')
                else:
                    # No items were received, delete the receipt
                    receipt.delete()
                    messages.warning(request, 'Es wurden keine Artikel als empfangen markiert.')

                return redirect('order_split_detail', pk=order.pk, split_id=split.pk)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            messages.error(request, f'Fehler beim Speichern des Wareneingangs: {str(e)}')

    # Get the items in this split
    split_items = split.items.select_related('order_item__product').all()

    context = {
        'order': order,
        'split': split,
        'split_items': split_items,
        'warehouses': warehouses,
        'has_batch_products': has_batch_products,
        'has_expiry_products': has_expiry_products,
    }

    return render(request, 'order/receive_order_split.html', context)


def update_order_status(order):
    """
    Aktualisiert den Status einer Bestellung basierend auf dem Wareneingangsstatus aller Positionen.
    """
    # Prüfen, ob alle Artikel vollständig erhalten wurden oder teilweise erhalten wurden
    all_items_fully_received = True
    any_items_received = False

    for item in order.items.all():
        # Stornierte Positionen überspringen
        if item.is_canceled:
            continue

        if item.quantity_received >= item.quantity_ordered:
            any_items_received = True
        else:
            all_items_fully_received = False
            if item.quantity_received > 0:
                any_items_received = True

    # Status setzen basierend auf dem Ergebnis
    if all_items_fully_received:
        order.status = 'received'
    elif any_items_received:
        order.status = 'partially_received'
    order.save()

    # Auch den Status aller zugehörigen Teillieferungen aktualisieren
    for split in order.splits.all():
        all_split_items_received = True

        for split_item in split.items.all():
            order_item = split_item.order_item
            if order_item.quantity_received < split_item.quantity:
                all_split_items_received = False
                break

        if all_split_items_received:
            split.status = 'received'
        else:
            # Wenn es bereits Wareneingänge gibt, aber nicht alle
            if any(receipt.items.exists() for receipt in split.receipts.all()):
                split.status = 'partially_received'

        split.save()


def update_order_status_after_receipt(order):
    """
    Updates the order status after a receipt is processed or deleted.
    Takes into account cancelled items and quality issues.
    """
    # Bestehende Prüfung für Vollständigkeit der Lieferung
    all_items_received = True
    any_items_received = False

    for item in order.items.all():
        # Stornierte Positionen überspringen
        if item.is_canceled:
            continue

        effective_ordered = item.effective_quantity

        if item.quantity_received >= effective_ordered:
            any_items_received = True
        else:
            all_items_received = False
            if item.quantity_received > 0:
                any_items_received = True

    # Prüfen, ob es aktive RMAs für diese Bestellung gibt
    has_active_rmas = RMA.objects.filter(
        related_order=order,
        status__in=['draft', 'pending', 'approved', 'sent']
    ).exists()

    # Status basierend auf Lieferstatus und RMAs setzen
    if all_items_received:
        if has_active_rmas:
            order.status = 'received_with_issues'
        else:
            order.status = 'received'
    elif any_items_received:
        order.status = 'partially_received'
    else:
        order.status = 'sent'

    if order.status == 'received_with_issues' and not any_items_received:
        order.status = 'sent'

    order.save()

    # Also update the status of all associated splits
    for split in order.splits.all():
        all_split_items_received = True
        any_split_items_received = False

        for split_item in split.items.select_related('order_item').all():
            order_item = split_item.order_item

            # Calculate how much of this split item has been received
            # This is complex because receipts are linked to order items, not split items
            total_received = order_item.quantity_received

            if total_received >= split_item.quantity:
                any_split_items_received = True
            else:
                all_split_items_received = False
                if total_received > 0:
                    any_split_items_received = True

        # Update split status
        if all_split_items_received:
            split.status = 'received'
        elif any_split_items_received:
            split.status = 'partially_received'
        elif split.status == 'received' or split.status == 'partially_received':
            # If it was previously received but now isn't, reset to planned
            split.status = 'planned'

        split.save()


# Ajax-Endpunkt, um zu prüfen ob eine Bestellung Teillieferungen hat
def check_order_has_splits(request, pk):
    """
    AJAX-Endpunkt, der prüft, ob eine Bestellung bereits Teillieferungen hat.
    """
    if request.method == 'GET':
        order = get_object_or_404(PurchaseOrder, pk=pk)
        has_splits = order.splits.exists()

        # Details zu vorhandenen Teillieferungen zurückgeben
        splits_data = []
        if has_splits:
            for split in order.splits.all():
                splits_data.append({
                    'id': split.id,
                    'name': split.name,
                    'status': split.get_status_display(),
                    'expected_delivery': split.expected_delivery.isoformat() if split.expected_delivery else None,
                    'items_count': split.items.count()
                })

        return JsonResponse({
            'has_splits': has_splits,
            'splits': splits_data
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
@permission_required('order', 'edit')
def order_split_update_status(request, pk, split_id):
    """Update the status of an order split."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    split = get_object_or_404(OrderSplit, pk=split_id, purchase_order=order)

    if request.method == 'POST':
        new_status = request.POST.get('status')

        # Validate status
        if new_status in dict(OrderSplit.SPLIT_STATUS_CHOICES):
            split.status = new_status
            split.save()

            status_display = dict(OrderSplit.SPLIT_STATUS_CHOICES)[new_status]
            messages.success(request, f'Status der Teillieferung "{split.name}" wurde auf "{status_display}" geändert.')
        else:
            messages.error(request, 'Ungültiger Status.')

        return redirect('order_split_detail', pk=order.pk, split_id=split.pk)

    # If not a POST request, redirect to the detail page
    return redirect('order_split_detail', pk=order.pk, split_id=split.pk)


@login_required
def check_order_splits(request, pk):
    """
    AJAX endpoint that checks if an order has any planned splits.
    Returns data about existing splits.
    """
    if request.method == 'GET':
        order = get_object_or_404(PurchaseOrder, pk=pk)
        splits = order.splits.exclude(status='received').order_by('expected_delivery')

        # Get split details for the response
        splits_data = []
        if splits.exists():
            for split in splits:
                splits_data.append({
                    'id': split.id,
                    'name': split.name,
                    'status': split.get_status_display(),
                    'expected_delivery': split.expected_delivery.isoformat() if split.expected_delivery else None,
                    'items_count': split.items.count()
                })

        return JsonResponse({
            'has_splits': splits.exists(),
            'splits': splits_data
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)



@login_required
@permission_required('order', 'view')
def purchase_order_comments(request, pk):
    """View for displaying all comments for an order."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'created_by'),
        pk=pk
    )

    # Get all comments
    comments = order.comments.select_related('user').order_by('-created_at')

    # Add filter capabilities
    comment_type = request.GET.get('type', '')
    if comment_type:
        comments = comments.filter(comment_type=comment_type)

    # Search functionality
    search = request.GET.get('search', '')
    if search:
        comments = comments.filter(comment__icontains=search)

    # Date range filtering
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            comments = comments.filter(created_at__gte=from_date)
        except ValueError:
            pass

    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            to_date = to_date.replace(hour=23, minute=59, second=59)
            comments = comments.filter(created_at__lte=to_date)
        except ValueError:
            pass

    context = {
        'order': order,
        'comments': comments,
        'comment_type': comment_type,
        'search': search,
        'date_from': date_from,
        'date_to': date_to,
    }

    return render(request, 'order/purchase_order_comments.html', context)


@login_required
@permission_required('order', 'edit')
def add_order_comment(request, pk):
    """Add a comment to a purchase order."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    if request.method == 'POST':
        comment_text = request.POST.get('comment', '').strip()
        is_public = request.POST.get('is_public', 'off') == 'on'
        attachment = request.FILES.get('attachment', None)

        if comment_text:
            comment = PurchaseOrderComment.objects.create(
                purchase_order=order,
                user=request.user,
                comment_type='note',
                comment=comment_text,
                is_public=is_public
            )

            # Handle attachment if present
            if attachment:
                comment.attachment = attachment
                comment.attachment_name = attachment.name
                comment.save()

            messages.success(request, 'Kommentar wurde erfolgreich hinzugefügt.')

            # If this is an AJAX request, return JSON
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'comment_id': comment.id,
                    'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M'),
                    'username': request.user.username,
                    'comment': comment_text,
                    'is_public': is_public,
                    'attachment_name': comment.attachment_name if attachment else None,
                    'attachment_url': comment.attachment.url if attachment else None,
                })
        else:
            messages.error(request, 'Der Kommentar darf nicht leer sein.')
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Der Kommentar darf nicht leer sein.'})

    # For non-AJAX requests or GET requests
    return redirect('purchase_order_detail', pk=order.pk)


@login_required
@permission_required('order', 'delete')
def delete_order_comment(request, pk, comment_id):
    """Delete a comment from a purchase order."""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    comment = get_object_or_404(PurchaseOrderComment, pk=comment_id, purchase_order=order)

    # Only allow deletion of user's own comments or if user has admin privileges
    if comment.user == request.user or request.user.has_perm('order.admin'):
        comment.delete()
        messages.success(request, 'Kommentar wurde gelöscht.')
    else:
        messages.error(request, 'Sie haben keine Berechtigung, diesen Kommentar zu löschen.')

    # If this is an AJAX request, return JSON
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True if not messages.get_messages(request) else False
        })

    # Redirect back to where the user came from
    return redirect(request.META.get('HTTP_REFERER', 'purchase_order_detail') + f'?tab=comments')