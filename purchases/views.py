from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum, F, ExpressionWrapper, DecimalField, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings

from core.models import Product, ProductWarehouse
from core.decorators import permission_required
from suppliers.models import Supplier, SupplierProduct
from inventory.models import Warehouse, StockMovement
from inventory.utils import user_has_warehouse_access

from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrderTemplate,
    PurchaseOrderTemplateItem,
    PurchaseRecommendation
)
from .forms import (
    PurchaseOrderForm,
    PurchaseOrderItemForm,
    PurchaseOrderItemFormSet,
    GoodsReceiptForm,
    GoodsReceiptItemForm,
    GoodsReceiptItemFormSet,
    PurchaseOrderTemplateForm,
    PurchaseOrderTemplateItemForm,
    PurchaseOrderTemplateItemFormSet,
    RecommendationFilterForm,
    EmailPurchaseOrderForm
)


# Purchase Order Views
@login_required
@permission_required('purchase', 'view')
def purchase_order_list(request):
    """List all purchase orders with filtering options."""
    # Base queryset
    orders = PurchaseOrder.objects.all().select_related('supplier', 'created_by')

    # Filter by status
    status = request.GET.get('status', '')
    if status:
        orders = orders.filter(status=status)

    # Filter by supplier
    supplier_id = request.GET.get('supplier', '')
    if supplier_id:
        orders = orders.filter(supplier_id=supplier_id)

    # Filter by date range
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if date_from:
        orders = orders.filter(order_date__gte=date_from)
    if date_to:
        orders = orders.filter(order_date__lte=date_to)

    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query) |
            Q(supplier__name__icontains=search_query) |
            Q(reference__icontains=search_query) |
            Q(notes__icontains=search_query)
        )

    # Order by
    order_by = request.GET.get('order_by', '-order_date')
    orders = orders.order_by(order_by)

    # Pagination
    paginator = Paginator(orders, 25)  # Show 25 orders per page
    page = request.GET.get('page')
    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    # Context for template
    context = {
        'orders': orders,
        'suppliers': Supplier.objects.all(),
        'status_choices': PurchaseOrder.STATUS_CHOICES,
        'status': status,
        'supplier_id': supplier_id,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'order_by': order_by
    }

    return render(request, 'purchases/purchase_order_list.html', context)


@login_required
@permission_required('purchase', 'view')
def purchase_order_detail(request, pk):
    """Show details of a specific purchase order."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'created_by'),
        pk=pk
    )

    # Get all items for this order
    items = order.items.all().select_related('product')

    # Get goods receipts for this order
    receipts = order.goods_receipts.all().select_related('created_by')

    context = {
        'order': order,
        'items': items,
        'receipts': receipts,
    }

    return render(request, 'purchases/purchase_order_detail.html', context)


@login_required
@permission_required('purchase', 'create')
def purchase_order_create(request):
    """Create a new purchase order."""
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Save the order with the current user
                order = form.save(commit=False)
                order.created_by = request.user
                order.save()

                # Process the formset
                formset = PurchaseOrderItemFormSet(request.POST, instance=order)
                if formset.is_valid():
                    formset.save()

                    # Calculate totals
                    order.save()  # This will recalculate subtotal and total

                    messages.success(request, f'Bestellung {order.order_number} wurde erfolgreich erstellt.')
                    return redirect('purchase_order_detail', pk=order.pk)
                else:
                    # If formset is invalid, show errors
                    for form in formset:
                        if form.errors:
                            for field, error in form.errors.items():
                                messages.error(request, f'{field}: {error[0]}')
        else:
            for field, error in form.errors.items():
                messages.error(request, f'{field}: {error[0]}')
    else:
        form = PurchaseOrderForm()
        formset = PurchaseOrderItemFormSet()

    context = {
        'form': form,
        'formset': formset,
        'suppliers': Supplier.objects.all(),
    }

    return render(request, 'purchases/purchase_order_form.html', context)


@login_required
@permission_required('purchase', 'edit')
def purchase_order_update(request, pk):
    """Update an existing purchase order."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Only draft orders can be edited
    if order.status != 'draft':
        messages.error(request, 'Nur Bestellungen im Status "Entwurf" können bearbeitet werden.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=order)
        if form.is_valid():
            with transaction.atomic():
                order = form.save()

                # Process the formset
                formset = PurchaseOrderItemFormSet(request.POST, instance=order)
                if formset.is_valid():
                    formset.save()

                    # Recalculate totals
                    order.save()

                    messages.success(request, f'Bestellung {order.order_number} wurde erfolgreich aktualisiert.')
                    return redirect('purchase_order_detail', pk=order.pk)
                else:
                    # If formset is invalid, show errors
                    for form in formset:
                        if form.errors:
                            for field, error in form.errors.items():
                                messages.error(request, f'{field}: {error[0]}')
        else:
            for field, error in form.errors.items():
                messages.error(request, f'{field}: {error[0]}')
    else:
        form = PurchaseOrderForm(instance=order)
        formset = PurchaseOrderItemFormSet(instance=order)

    context = {
        'form': form,
        'formset': formset,
        'order': order,
        'suppliers': Supplier.objects.all(),
    }

    return render(request, 'purchases/purchase_order_form.html', context)


@login_required
@permission_required('purchase', 'delete')
def purchase_order_delete(request, pk):
    """Delete a purchase order."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Only draft orders can be deleted
    if order.status != 'draft':
        messages.error(request, 'Nur Bestellungen im Status "Entwurf" können gelöscht werden.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        order_number = order.order_number
        order.delete()
        messages.success(request, f'Bestellung {order_number} wurde erfolgreich gelöscht.')
        return redirect('purchase_order_list')

    context = {
        'order': order,
    }

    return render(request, 'purchases/purchase_order_confirm_delete.html', context)


@login_required
@permission_required('purchase', 'edit')
def purchase_order_mark_sent(request, pk):
    """Mark a purchase order as sent."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Only draft orders can be marked as sent
    if order.status != 'draft':
        messages.error(request, 'Nur Bestellungen im Status "Entwurf" können als bestellt markiert werden.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        # Set order status to sent and save order date if not already set
        order.status = 'sent'
        if not order.order_date:
            order.order_date = timezone.now().date()
        order.save()

        # Update any purchase recommendations linked to items in this order
        for item in order.items.all():
            recommendations = PurchaseRecommendation.objects.filter(
                product=item.product,
                status__in=['new', 'in_process']
            )
            for rec in recommendations:
                rec.status = 'ordered'
                rec.purchase_order = order
                rec.save()

        messages.success(request, f'Bestellung {order.order_number} wurde als "Bestellt" markiert.')
        return redirect('purchase_order_detail', pk=order.pk)

    context = {
        'order': order,
    }

    return render(request, 'purchases/purchase_order_mark_sent.html', context)


@login_required
@permission_required('purchase', 'edit')
def purchase_order_cancel(request, pk):
    """Cancel a purchase order."""
    order = get_object_or_404(PurchaseOrder, pk=pk)

    # Only sent or partially received orders can be cancelled
    if order.status not in ['sent', 'partially_received']:
        messages.error(request,
                       'Nur Bestellungen im Status "Bestellt" oder "Teilweise erhalten" können storniert werden.')
        return redirect('purchase_order_detail', pk=order.pk)

    if request.method == 'POST':
        # Set order status to cancelled
        order.status = 'cancelled'
        order.save()

        messages.success(request, f'Bestellung {order.order_number} wurde storniert.')
        return redirect('purchase_order_detail', pk=order.pk)

    context = {
        'order': order,
    }

    return render(request, 'purchases/purchase_order_cancel.html', context)


@login_required
@permission_required('purchase', 'edit')
def purchase_order_item_add(request, order_id):
    """Add a new item to a purchase order."""
    order = get_object_or_404(PurchaseOrder, pk=order_id)

    # Only draft orders can be edited
    if order.status != 'draft':
        messages.error(request, 'Nur Bestellungen im Status "Entwurf" können bearbeitet werden.')
        return redirect('purchase_order_detail', pk=order_id)

    if request.method == 'POST':
        form = PurchaseOrderItemForm(request.POST, supplier=order.supplier)
        if form.is_valid():
            item = form.save(commit=False)
            item.purchase_order = order
            item.save()

            # Recalculate order totals
            order.save()

            messages.success(request, 'Artikel wurde der Bestellung hinzugefügt.')
            return redirect('purchase_order_detail', pk=order_id)
        else:
            for field, error in form.errors.items():
                messages.error(request, f'{field}: {error[0]}')
    else:
        form = PurchaseOrderItemForm(supplier=order.supplier)

    context = {
        'form': form,
        'order': order,
    }

    return render(request, 'purchases/purchase_order_item_form.html', context)


@login_required
@permission_required('purchase', 'edit')
def purchase_order_item_update(request, order_id, item_id):
    """Update an item in a purchase order."""
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    item = get_object_or_404(PurchaseOrderItem, pk=item_id, purchase_order=order)

    # Only draft orders can be edited
    if order.status != 'draft':
        messages.error(request, 'Nur Bestellungen im Status "Entwurf" können bearbeitet werden.')
        return redirect('purchase_order_detail', pk=order_id)

    if request.method == 'POST':
        form = PurchaseOrderItemForm(request.POST, instance=item, supplier=order.supplier)
        if form.is_valid():
            form.save()

            # Recalculate order totals
            order.save()

            messages.success(request, 'Artikel wurde aktualisiert.')
            return redirect('purchase_order_detail', pk=order_id)
        else:
            for field, error in form.errors.items():
                messages.error(request, f'{field}: {error[0]}')
    else:
        form = PurchaseOrderItemForm(instance=item, supplier=order.supplier)

    context = {
        'form': form,
        'order': order,
        'item': item,
    }

    return render(request, 'purchases/purchase_order_item_form.html', context)


@login_required
@permission_required('purchase', 'delete')
def purchase_order_item_delete(request, order_id, item_id):
    """Remove an item from a purchase order."""
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    item = get_object_or_404(PurchaseOrderItem, pk=item_id, purchase_order=order)

    # Only draft orders can be edited
    if order.status != 'draft':
        messages.error(request, 'Nur Bestellungen im Status "Entwurf" können bearbeitet werden.')
        return redirect('purchase_order_detail', pk=order_id)

    if request.method == 'POST':
        product_name = item.product.name
        item.delete()

        # Recalculate order totals
        order.save()

        messages.success(request, f'Artikel "{product_name}" wurde aus der Bestellung entfernt.')
        return redirect('purchase_order_detail', pk=order_id)

    context = {
        'order': order,
        'item': item,
    }

    return render(request, 'purchases/purchase_order_item_confirm_delete.html', context)


@login_required
@permission_required('purchase', 'view')
def purchase_order_print(request, pk):
    """Generate a printable version of the purchase order."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'created_by'),
        pk=pk
    )

    # Get all items for this order
    items = order.items.all().select_related('product')

    context = {
        'order': order,
        'items': items,
        'company_name': getattr(settings, 'COMPANY_NAME', 'Ihr Unternehmen'),
        'company_address': getattr(settings, 'COMPANY_ADDRESS', 'Ihre Adresse'),
        'company_phone': getattr(settings, 'COMPANY_PHONE', 'Ihre Telefonnummer'),
        'company_email': getattr(settings, 'COMPANY_EMAIL', 'Ihre E-Mail'),
        'company_website': getattr(settings, 'COMPANY_WEBSITE', 'Ihre Website'),
        'company_tax_id': getattr(settings, 'COMPANY_TAX_ID', 'Ihre Steuernummer'),
    }

    return render(request, 'purchases/purchase_order_print.html', context)


@login_required
@permission_required('purchase', 'edit')
def purchase_order_email(request, pk):
    """Email a purchase order to the supplier."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'created_by'),
        pk=pk
    )

    # Get the supplier email if available
    initial_email = order.supplier.email if order.supplier.email else ''

    if request.method == 'POST':
        form = EmailPurchaseOrderForm(request.POST)
        if form.is_valid():
            recipient = form.cleaned_data['recipient']
            cc = form.cleaned_data['cc']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            attach_pdf = form.cleaned_data['attach_pdf']

            try:
                # Create email
                email = EmailMessage(
                    subject=subject,
                    body=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient],
                    cc=[cc] if cc else [],
                )

                # Attach PDF if requested
                if attach_pdf:
                    # You would need to implement PDF generation and attach it here
                    # This is a placeholder to show the concept
                    # pdf_content = generate_pdf(order)
                    # email.attach(f'Bestellung_{order.order_number}.pdf', pdf_content, 'application/pdf')
                    pass

                # Send email
                email.send()

                # Mark order as sent if it's still in draft
                if order.status == 'draft':
                    order.status = 'sent'
                    if not order.order_date:
                        order.order_date = timezone.now().date()
                    order.save()

                messages.success(request, f'Die Bestellung wurde erfolgreich an {recipient} gesendet.')
                return redirect('purchase_order_detail', pk=order.pk)

            except Exception as e:
                messages.error(request, f'Fehler beim Senden der E-Mail: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        # Initialize form with defaults
        initial = {
            'recipient': initial_email,
            'subject': f'Bestellung {order.order_number}',
            'message': render_to_string('purchases/email/purchase_order_email_template.txt', {
                'order': order,
                'company_name': getattr(settings, 'COMPANY_NAME', 'Ihr Unternehmen'),
            }),
        }
        form = EmailPurchaseOrderForm(initial=initial)

    context = {
        'form': form,
        'order': order,
    }

    return render(request, 'purchases/purchase_order_email.html', context)


@login_required
@permission_required('purchase', 'create')
def purchase_order_create_from_template(request, template_id):
    """Create a new purchase order from a template."""
    template = get_object_or_404(
        PurchaseOrderTemplate.objects.select_related('supplier'),
        pk=template_id
    )

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Create new order
                order = form.save(commit=False)
                order.created_by = request.user
                order.save()

                # Add items from template
                for template_item in template.items.all():
                    # Get current price from supplier_product if it exists
                    unit_price = 0
                    supplier_sku = ''

                    if template_item.supplier_product:
                        unit_price = template_item.supplier_product.purchase_price
                        supplier_sku = template_item.supplier_product.supplier_sku

                    PurchaseOrderItem.objects.create(
                        purchase_order=order,
                        product=template_item.product,
                        supplier_product=template_item.supplier_product,
                        quantity=template_item.quantity,
                        unit_price=unit_price,
                        supplier_sku=supplier_sku
                    )

                # Update totals
                order.save()

                messages.success(request, f'Bestellung {order.order_number} wurde aus Vorlage erstellt.')
                return redirect('purchase_order_detail', pk=order.pk)
        else:
            for field, error in form.errors.items():
                messages.error(request, f'{field}: {error[0]}')
    else:
        # Pre-fill form with supplier from template
        initial = {
            'supplier': template.supplier,
            'shipping_address': template.supplier.address,
            'notes': template.notes,
        }
        form = PurchaseOrderForm(initial=initial)

    context = {
        'form': form,
        'template': template,
        'template_items': template.items.all(),
    }

    return render(request, 'purchases/purchase_order_from_template.html', context)


@login_required
@permission_required('purchase', 'create')
def purchase_order_create_from_recommendations(request):
    """Create a new purchase order from purchase recommendations."""
    # Get selected recommendations from query params
    recommendation_ids = request.GET.getlist('recommendations')

    if not recommendation_ids:
        messages.error(request, 'Keine Empfehlungen ausgewählt.')
        return redirect('purchase_recommendation_list')

    # Get all selected recommendations
    recommendations = PurchaseRecommendation.objects.filter(
        id__in=recommendation_ids,
        status__in=['new', 'in_process']
    ).select_related('product', 'supplier_product')

    # Group by supplier
    suppliers = {}
    for rec in recommendations:
        supplier = None
        if rec.supplier_product:
            supplier = rec.supplier_product.supplier

        if supplier:
            if supplier.id not in suppliers:
                suppliers[supplier.id] = {
                    'supplier': supplier,
                    'recommendations': []
                }
            suppliers[supplier.id]['recommendations'].append(rec)

    # If more than one supplier, ask user to select one
    if len(suppliers) > 1:
        context = {
            'suppliers': suppliers.values(),
            'recommendation_ids': ','.join(recommendation_ids),
        }
        return render(request, 'purchases/select_supplier.html', context)

    # If only one supplier or supplier selected
    supplier_id = request.GET.get('supplier')
    if supplier_id:
        supplier = Supplier.objects.get(pk=supplier_id)
        selected_recommendations = []
        for rec_id in recommendation_ids:
            try:
                rec = PurchaseRecommendation.objects.get(pk=rec_id)
                if rec.supplier_product and rec.supplier_product.supplier.id == int(supplier_id):
                    selected_recommendations.append(rec)
            except PurchaseRecommendation.DoesNotExist:
                continue
    else:
        # Only one supplier
        if suppliers:
            first_supplier = list(suppliers.values())[0]
            supplier = first_supplier['supplier']
            selected_recommendations = first_supplier['recommendations']
        else:
            messages.error(request, 'Keine Empfehlungen mit gültigem Lieferanten gefunden.')
            return redirect('purchase_recommendation_list')

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Create new order
                order = form.save(commit=False)
                order.created_by = request.user
                order.save()

                # Add items from recommendations
                for rec in selected_recommendations:
                    # Get price and SKU from supplier_product if it exists
                    unit_price = 0
                    supplier_sku = ''

                    if rec.supplier_product:
                        unit_price = rec.supplier_product.purchase_price
                        supplier_sku = rec.supplier_product.supplier_sku

                    PurchaseOrderItem.objects.create(
                        purchase_order=order,
                        product=rec.product,
                        supplier_product=rec.supplier_product,
                        quantity=rec.recommended_quantity,
                        unit_price=unit_price,
                        supplier_sku=supplier_sku
                    )

                    # Update recommendation status
                    rec.status = 'in_process'
                    rec.purchase_order = order
                    rec.save()

                # Update totals
                order.save()

                messages.success(request, f'Bestellung {order.order_number} wurde aus Empfehlungen erstellt.')
                return redirect('purchase_order_detail', pk=order.pk)
        else:
            for field, error in form.errors.items():
                messages.error(request, f'{field}: {error[0]}')
    else:
        # Pre-fill form with supplier
        initial = {
            'supplier': supplier,
            'shipping_address': supplier.address,
        }
        form = PurchaseOrderForm(initial=initial)

    context = {
        'form': form,
        'supplier': supplier,
        'recommendations': selected_recommendations,
    }

    return render(request, 'purchases/purchase_order_from_recommendations.html', context)


# Goods Receipt Views
@login_required
@permission_required('purchase', 'view')
def goods_receipt_list(request):
    """List all goods receipts with filtering options."""
    # Base queryset
    receipts = GoodsReceipt.objects.all().select_related('purchase_order', 'created_by')

    # Filter by status
    status = request.GET.get('status', '')
    if status:
        receipts = receipts.filter(status=status)

    # Filter by purchase order
    order_id = request.GET.get('order', '')
    if order_id:
        receipts = receipts.filter(purchase_order_id=order_id)

    # Filter by date range
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if date_from:
        receipts = receipts.filter(receipt_date__gte=date_from)
    if date_to:
        receipts = receipts.filter(receipt_date__lte=date_to)

    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        receipts = receipts.filter(
            Q(receipt_number__icontains=search_query) |
            Q(delivery_note_number__icontains=search_query) |
            Q(purchase_order__order_number__icontains=search_query) |
            Q(notes__icontains=search_query)
        )

    # Order by
    order_by = request.GET.get('order_by', '-receipt_date')
    receipts = receipts.order_by(order_by)

    # Pagination
    paginator = Paginator(receipts, 25)  # Show 25 receipts per page
    page = request.GET.get('page')
    try:
        receipts = paginator.page(page)
    except PageNotAnInteger:
        receipts = paginator.page(1)
    except EmptyPage:
        receipts = paginator.page(paginator.num_pages)

    # Context for template
    context = {
        'receipts': receipts,
        'purchase_orders': PurchaseOrder.objects.filter(status__in=['sent', 'partially_received']),
        'status_choices': GoodsReceipt.STATUS_CHOICES,
        'status': status,
        'order_id': order_id,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'order_by': order_by
    }

    return render(request, 'purchases/goods_receipt_list.html', context)


@login_required
@permission_required('purchase', 'view')
def goods_receipt_detail(request, pk):
    """Show details of a specific goods receipt."""
    receipt = get_object_or_404(
        GoodsReceipt.objects.select_related('purchase_order', 'created_by'),
        pk=pk
    )

    # Get all items for this receipt
    items = receipt.items.all().select_related('purchase_order_item', 'purchase_order_item__product')

    context = {
        'receipt': receipt,
        'items': items,
    }

    return render(request, 'purchases/goods_receipt_detail.html', context)


@login_required
@permission_required('purchase', 'create')
def goods_receipt_create(request, order_id):
    """Create a new goods receipt for a purchase order."""
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier'),
        pk=order_id
    )

    # Only sent or partially received orders can have goods receipts
    if purchase_order.status not in ['sent', 'partially_received']:
        messages.error(request,
                       'Nur Bestellungen im Status "Bestellt" oder "Teilweise erhalten" können Wareneingänge haben.')
        return redirect('purchase_order_detail', pk=order_id)

    # Get all items that haven't been fully received
    unreceived_items = purchase_order.items.filter(
        quantity__gt=F('received_quantity')
    ).select_related('product')

    if not unreceived_items:
        messages.warning(request, 'Alle Artikel dieser Bestellung wurden bereits vollständig erhalten.')
        return redirect('purchase_order_detail', pk=order_id)

    if request.method == 'POST':
        form = GoodsReceiptForm(request.POST)

        # Create formset with initial data
        formset = GoodsReceiptItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                # Save the receipt with current user
                receipt = form.save(commit=False)
                receipt.purchase_order = purchase_order
                receipt.created_by = request.user
                receipt.save()

                # Process formset
                formset = GoodsReceiptItemFormSet(request.POST, instance=receipt)
                if formset.is_valid():
                    formset.save()

                    # Check if the receipt should be completed
                    if 'complete' in request.POST:
                        receipt.status = 'completed'
                        receipt.save()

                        # Process stock movements
                        for item in receipt.items.all():
                            if item.received_quantity > 0 and not item.is_defective:
                                # Create stock movement
                                warehouse = form.cleaned_data.get('warehouse')
                                if warehouse and user_has_warehouse_access(request.user, warehouse, 'manage_stock'):
                                    StockMovement.objects.create(
                                        product=item.purchase_order_item.product,
                                        warehouse=warehouse,
                                        quantity=item.received_quantity,
                                        movement_type='in',
                                        reference=f'Wareneingang {receipt.receipt_number}',
                                        notes=f'Aus Bestellung {purchase_order.order_number}',
                                        created_by=request.user
                                    )

                                    # Update product stock in warehouse
                                    try:
                                        pw = ProductWarehouse.objects.get(
                                            product=item.purchase_order_item.product,
                                            warehouse=warehouse
                                        )
                                        pw.quantity += item.received_quantity
                                        pw.save()
                                    except ProductWarehouse.DoesNotExist:
                                        ProductWarehouse.objects.create(
                                            product=item.purchase_order_item.product,
                                            warehouse=warehouse,
                                            quantity=item.received_quantity
                                        )

                                    # Update product's overall stock
                                    product = item.purchase_order_item.product
                                    total_stock = ProductWarehouse.objects.filter(
                                        product=product
                                    ).aggregate(total=Sum('quantity'))['total'] or 0
                                    product.current_stock = total_stock
                                    product.save()

                                # Update received quantity on purchase order item
                                po_item = item.purchase_order_item
                                po_item.received_quantity += item.received_quantity
                                po_item.save()

                        # Update purchase order status
                        purchase_order.update_status_based_on_items()

                    messages.success(request, f'Wareneingang {receipt.receipt_number} wurde erfolgreich erstellt.')
                    return redirect('goods_receipt_detail', pk=receipt.pk)
                else:
                    for form in formset:
                        if form.errors:
                            for field, error in form.errors.items():
                                messages.error(request, f'{field}: {error[0]}')
        else:
            for field, error in form.errors.items():
                messages.error(request, f'{field}: {error[0]}')
    else:
        form = GoodsReceiptForm()

        # Create initial data for the formset - one entry per unreceived item
        initial_data = []
        for item in unreceived_items:
            initial_data.append({
                'purchase_order_item': item.id,
                'received_quantity': item.quantity - item.received_quantity,  # Default to remaining quantity
            })

        formset = GoodsReceiptItemFormSet(initial=initial_data)

    # Accessible warehouses for the user
    accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                             if user_has_warehouse_access(request.user, w, 'manage_stock')]

    context = {
        'form': form,
        'formset': formset,
        'purchase_order': purchase_order,
        'unreceived_items': unreceived_items,
        'warehouses': accessible_warehouses,
    }

    return render(request, 'purchases/goods_receipt_form.html', context)


@login_required
@permission_required('purchase', 'edit')
def goods_receipt_update(request, pk):
    """Update a goods receipt."""
    receipt = get_object_or_404(GoodsReceipt, pk=pk)

    # Only draft receipts can be edited
    if receipt.status != 'draft':
        messages.error(request, 'Nur Wareneingänge im Status "Entwurf" können bearbeitet werden.')
        return redirect('goods_receipt_detail', pk=receipt.pk)

    if request.method == 'POST':
        form = GoodsReceiptForm(request.POST, instance=receipt)
        formset = GoodsReceiptItemFormSet(request.POST, instance=receipt)

        if form.is_valid() and formset.is_valid():
            receipt = form.save()
            formset.save()

            # Check if the receipt should be completed
            if 'complete' in request.POST:
                receipt.status = 'completed'
                receipt.save()

                # Process stock movements and update PO item quantities
                # (Logic similar to goods_receipt_create)

            messages.success(request, f'Wareneingang {receipt.receipt_number} wurde aktualisiert.')
            return redirect('goods_receipt_detail', pk=receipt.pk)
        else:
            for field, error in form.errors.items():
                messages.error(request, f'{field}: {error[0]}')
            for form in formset:
                if form.errors:
                    for field, error in form.errors.items():
                        messages.error(request, f'{field}: {error[0]}')
    else:
        form = GoodsReceiptForm(instance=receipt)
        formset = GoodsReceiptItemFormSet(instance=receipt)

    # Accessible warehouses for the user
    accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                             if user_has_warehouse_access(request.user, w, 'manage_stock')]

    context = {
        'form': form,
        'formset': formset,
        'receipt': receipt,
        'purchase_order': receipt.purchase_order,
        'warehouses': accessible_warehouses,
    }

    return render(request, 'purchases/goods_receipt_form.html', context)


@login_required
@permission_required('purchase', 'edit')
def goods_receipt_complete(request, pk):
    """Complete a goods receipt."""
    receipt = get_object_or_404(GoodsReceipt, pk=pk)

    # Only draft receipts can be completed
    if receipt.status != 'draft':
        messages.error(request, 'Nur Wareneingänge im Status "Entwurf" können abgeschlossen werden.')
        return redirect('goods_receipt_detail', pk=receipt.pk)

    if request.method == 'POST':
        warehouse_id = request.POST.get('warehouse')

        try:
            warehouse = Warehouse.objects.get(pk=warehouse_id)

            # Check warehouse access
            if not user_has_warehouse_access(request.user, warehouse, 'manage_stock'):
                messages.error(request, 'Sie haben keine Berechtigung für dieses Lager.')
                return redirect('goods_receipt_detail', pk=receipt.pk)

            with transaction.atomic():
                # Update receipt status
                receipt.status = 'completed'
                receipt.save()

                # Process each item
                for item in receipt.items.all():
                    if item.received_quantity > 0 and not item.is_defective:
                        # Create stock movement
                        StockMovement.objects.create(
                            product=item.purchase_order_item.product,
                            warehouse=warehouse,
                            quantity=item.received_quantity,
                            movement_type='in',
                            reference=f'Wareneingang {receipt.receipt_number}',
                            notes=f'Aus Bestellung {receipt.purchase_order.order_number}',
                            created_by=request.user
                        )

                        # Update product stock in warehouse
                        try:
                            pw = ProductWarehouse.objects.get(
                                product=item.purchase_order_item.product,
                                warehouse=warehouse
                            )
                            pw.quantity += item.received_quantity
                            pw.save()
                        except ProductWarehouse.DoesNotExist:
                            ProductWarehouse.objects.create(
                                product=item.purchase_order_item.product,
                                warehouse=warehouse,
                                quantity=item.received_quantity
                            )

                        # Update product's overall stock
                        product = item.purchase_order_item.product
                        total_stock = ProductWarehouse.objects.filter(
                            product=product
                        ).aggregate(total=Sum('quantity'))['total'] or 0
                        product.current_stock = total_stock
                        product.save()

                    # Update received quantity on purchase order item
                    po_item = item.purchase_order_item
                    po_item.received_quantity += item.received_quantity
                    po_item.save()

                # Update purchase order status
                receipt.purchase_order.update_status_based_on_items()

            messages.success(request, f'Wareneingang {receipt.receipt_number} wurde abgeschlossen.')
            return redirect('goods_receipt_detail', pk=receipt.pk)

        except Warehouse.DoesNotExist:
            messages.error(request, 'Das gewählte Lager existiert nicht.')

    # Get accessible warehouses
    accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                             if user_has_warehouse_access(request.user, w, 'manage_stock')]

    context = {
        'receipt': receipt,
        'warehouses': accessible_warehouses,
    }

    return render(request, 'purchases/goods_receipt_complete.html', context)


@login_required
@permission_required('purchase', 'edit')
def goods_receipt_cancel(request, pk):
    """Cancel a goods receipt."""
    receipt = get_object_or_404(GoodsReceipt, pk=pk)

    # Only draft receipts can be cancelled
    if receipt.status != 'draft':
        messages.error(request, 'Nur Wareneingänge im Status "Entwurf" können storniert werden.')
        return redirect('goods_receipt_detail', pk=receipt.pk)

    if request.method == 'POST':
        receipt.status = 'cancelled'
        receipt.save()

        messages.success(request, f'Wareneingang {receipt.receipt_number} wurde storniert.')
        return redirect('goods_receipt_detail', pk=receipt.pk)

    context = {
        'receipt': receipt,
    }

    return render(request, 'purchases/goods_receipt_cancel.html', context)


# Template Views
@login_required
@permission_required('purchase', 'view')
def purchase_order_template_list(request):
    """List all purchase order templates."""
    templates = PurchaseOrderTemplate.objects.all().select_related('supplier', 'created_by')

    # Filter by supplier
    supplier_id = request.GET.get('supplier', '')
    if supplier_id:
        templates = templates.filter(supplier_id=supplier_id)

    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        templates = templates.filter(
            Q(name__icontains=search_query) |
            Q(supplier__name__icontains=search_query) |
            Q(notes__icontains=search_query)
        )

    # Annotate with item count
    templates = templates.annotate(item_count=Count('items'))

    # Pagination
    paginator = Paginator(templates, 25)
    page = request.GET.get('page')
    try:
        templates = paginator.page(page)
    except PageNotAnInteger:
        templates = paginator.page(1)
    except EmptyPage:
        templates = paginator.page(paginator.num_pages)

    context = {
        'templates': templates,
        'suppliers': Supplier.objects.all(),
        'supplier_id': supplier_id,
        'search_query': search_query,
    }

    return render(request, 'purchases/template_list.html', context)


@login_required
@permission_required('purchase', 'view')
def purchase_order_template_detail(request, pk):
    """Show details of a purchase order template."""
    template = get_object_or_404(
        PurchaseOrderTemplate.objects.select_related('supplier', 'created_by'),
        pk=pk
    )

    # Get all items for this template
    items = template.items.all().select_related('product', 'supplier_product')

    context = {
        'template': template,
        'items': items,
    }

    return render(request, 'purchases/template_detail.html', context)


@login_required
@permission_required('purchase', 'create')
def purchase_order_template_create(request):
    """Create a new purchase order template."""
    if request.method == 'POST':
        form = PurchaseOrderTemplateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Save the template with the current user
                template = form.save(commit=False)
                template.created_by = request.user
                template.save()

                # Process the formset
                formset = PurchaseOrderTemplateItemFormSet(request.POST, instance=template)
                if formset.is_valid():
                    formset.save()

                    messages.success(request, f'Vorlage "{template.name}" wurde erfolgreich erstellt.')
                    return redirect('purchase_order_template_detail', pk=template.pk)
                else:
                    # If formset is invalid, show errors
                    for form in formset:
                        if form.errors:
                            for field, error in form.errors.items():
                                messages.error(request, f'{field}: {error[0]}')
        else:
            for field, error in form.errors.items():
                messages.error(request, f'{field}: {error[0]}')
    else:
        form = PurchaseOrderTemplateForm()
        formset = PurchaseOrderTemplateItemFormSet()

    context = {
        'form': form,
        'formset': formset,
        'suppliers': Supplier.objects.all(),
    }

    return render(request, 'purchases/template_form.html', context)


@login_required
@permission_required('purchase', 'edit')
def purchase_order_template_update(request, pk):
    """Update an existing purchase order template."""
    template = get_object_or_404(PurchaseOrderTemplate, pk=pk)

    if request.method == 'POST':
        form = PurchaseOrderTemplateForm(request.POST, instance=template)
        if form.is_valid():
            with transaction.atomic():
                template = form.save()

                # Process the formset
                formset = PurchaseOrderTemplateItemFormSet(request.POST, instance=template)
                if formset.is_valid():
                    formset.save()

                    messages.success(request, f'Vorlage "{template.name}" wurde erfolgreich aktualisiert.')
                    return redirect('purchase_order_template_detail', pk=template.pk)
                else:
                    # If formset is invalid, show errors
                    for form in formset:
                        if form.errors:
                            for field, error in form.errors.items():
                                messages.error(request, f'{field}: {error[0]}')
        else:
            for field, error in form.errors.items():
                messages.error(request, f'{field}: {error[0]}')
    else:
        form = PurchaseOrderTemplateForm(instance=template)
        formset = PurchaseOrderTemplateItemFormSet(instance=template)

    context = {
        'form': form,
        'formset': formset,
        'template': template,
        'suppliers': Supplier.objects.all(),
    }

    return render(request, 'purchases/template_form.html', context)


@login_required
@permission_required('purchase', 'delete')
def purchase_order_template_delete(request, pk):
    """Delete a purchase order template."""
    template = get_object_or_404(PurchaseOrderTemplate, pk=pk)

    if request.method == 'POST':
        template_name = template.name
        template.delete()
        messages.success(request, f'Vorlage "{template_name}" wurde erfolgreich gelöscht.')
        return redirect('purchase_order_template_list')

    context = {
        'template': template,
    }

    return render(request, 'purchases/template_confirm_delete.html', context)


# Recommendation Views
@login_required
@permission_required('purchase', 'view')
def purchase_recommendation_list(request):
    """List all purchase recommendations."""
    # Base queryset
    recommendations = PurchaseRecommendation.objects.all().select_related(
        'product', 'supplier_product', 'supplier_product__supplier', 'purchase_order'
    )

    # Get the form with request data
    form = RecommendationFilterForm(request.GET or None)

    # Apply filters if form is valid
    if form.is_valid():
        status = form.cleaned_data.get('status')
        supplier = form.cleaned_data.get('supplier')
        search = form.cleaned_data.get('search')

        if status:
            recommendations = recommendations.filter(status=status)

        if supplier:
            recommendations = recommendations.filter(supplier_product__supplier=supplier)

        if search:
            recommendations = recommendations.filter(
                Q(product__name__icontains=search) |
                Q(product__sku__icontains=search)
            )

    # Group by supplier for better organization
    # This is more complex and would normally be done in the template
    # or with a more sophisticated query

    # Pagination
    paginator = Paginator(recommendations, 50)
    page = request.GET.get('page')
    try:
        recommendations = paginator.page(page)
    except PageNotAnInteger:
        recommendations = paginator.page(1)
    except EmptyPage:
        recommendations = paginator.page(paginator.num_pages)

    context = {
        'recommendations': recommendations,
        'form': form,
    }

    return render(request, 'purchases/recommendation_list.html', context)


@login_required
@permission_required('purchase', 'create')
def generate_purchase_recommendations(request):
    """Generate purchase recommendations for all products."""
    if request.method == 'POST':
        # Get all products
        products = Product.objects.all()

        # Count of new recommendations
        new_count = 0
        updated_count = 0

        for product in products:
            # Skip if no minimum stock defined
            if product.minimum_stock <= 0:
                continue

            # Skip if current stock is above minimum
            if product.current_stock > product.minimum_stock:
                continue

            # Calculate recommended quantity
            # Default formula: twice the minimum stock minus current stock
            recommended_quantity = (product.minimum_stock * 2) - product.current_stock

            # Find preferred supplier
            supplier_product = product.supplier_products.filter(is_preferred=True).first()
            if not supplier_product:
                # If no preferred supplier, get the first one
                supplier_product = product.supplier_products.first()

            # Skip if no supplier available
            if not supplier_product:
                continue

            # Check for existing recommendations
            existing_rec = PurchaseRecommendation.objects.filter(
                product=product,
                status__in=['new', 'in_process']
            ).first()

            if existing_rec:
                # Update existing recommendation
                existing_rec.current_stock = product.current_stock
                existing_rec.min_stock = product.minimum_stock
                existing_rec.recommended_quantity = recommended_quantity
                existing_rec.supplier_product = supplier_product
                existing_rec.save()
                updated_count += 1
            else:
                # Create new recommendation
                PurchaseRecommendation.objects.create(
                    product=product,
                    supplier_product=supplier_product,
                    current_stock=product.current_stock,
                    min_stock=product.minimum_stock,
                    recommended_quantity=recommended_quantity
                )
                new_count += 1

        messages.success(
            request,
            f'Bestellvorschläge generiert: {new_count} neu, {updated_count} aktualisiert.'
        )
        return redirect('purchase_recommendation_list')

    # GET request - show confirmation form
    # Count how many recommendations would be generated
    low_stock_count = Product.objects.filter(
        current_stock__lt=F('minimum_stock'),
        minimum_stock__gt=0
    ).count()

    context = {
        'low_stock_count': low_stock_count,
    }

    return render(request, 'purchases/generate_recommendations.html', context)


@login_required
@permission_required('purchase', 'edit')
def update_recommendation_status(request, pk):
    """Update the status of a purchase recommendation."""
    recommendation = get_object_or_404(PurchaseRecommendation, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(PurchaseRecommendation.STATUS_CHOICES).keys():
            recommendation.status = new_status
            recommendation.save()

            # If using AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'status': new_status,
                    'status_display': dict(PurchaseRecommendation.STATUS_CHOICES)[new_status]
                })

            messages.success(request, 'Status wurde aktualisiert.')
            return redirect('purchase_recommendation_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Ungültiger Status'
                }, status=400)

            messages.error(request, 'Ungültiger Status')

    # For non-AJAX GET requests or invalid POST
    return redirect('purchase_recommendation_list')