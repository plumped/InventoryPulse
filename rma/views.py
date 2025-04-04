from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Sum
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.forms import modelformset_factory
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from accessmanagement.decorators import permission_required
from order.models import PurchaseOrder, PurchaseOrderReceiptItem, PurchaseOrderReceipt
from inventory.models import StockMovement, Warehouse
from suppliers.models import Supplier

from .models import (
    RMA, RMAItem, RMAStatus, RMAPhoto, RMAComment, RMAHistory,
    RMAResolutionType, RMAIssueType, RMADocument
)
from .forms import (
    RMAForm, RMAItemForm, RMAStatusUpdateForm, RMAResolutionForm,
    RMACommentForm, RMAFilterForm
)


def generate_rma_number(prefix="RMA"):
    """Generate a unique RMA number."""
    today = date.today()
    formatted_date = today.strftime("%Y%m%d")

    # Find the next sequence number
    last_rma = RMA.objects.filter(
        rma_number__startswith=f"{prefix}-{formatted_date}-"
    ).order_by('-rma_number').first()

    if last_rma:
        try:
            last_seq = int(last_rma.rma_number.split('-')[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1

    # Create new RMA number
    return f"{prefix}-{formatted_date}-{next_seq:03d}"


@login_required
@permission_required('rma', 'view')
def rma_list(request):
    """List all RMAs with filtering and search."""
    # Base queryset
    queryset = RMA.objects.select_related('supplier', 'created_by').prefetch_related('items')

    # Apply filters
    form = RMAFilterForm(request.GET or None)

    if form.is_valid():
        # Status filter
        status = form.cleaned_data.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Supplier filter
        supplier = form.cleaned_data.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier=supplier)

        # Date range filter
        date_from = form.cleaned_data.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        date_to = form.cleaned_data.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        # Search filter
        search = form.cleaned_data.get('search')
        if search:
            queryset = queryset.filter(
                Q(rma_number__icontains=search) |
                Q(items__product__name__icontains=search) |
                Q(supplier__name__icontains=search)
            ).distinct()

    # Sorting
    queryset = queryset.order_by('-created_at')

    # Calculate total value and item count
    for rma in queryset:
        rma.item_count = rma.items.count()

    # Pagination
    paginator = Paginator(queryset, 20)  # 20 RMAs per page
    page = request.GET.get('page')
    try:
        rmas = paginator.page(page)
        # Calculate page range
        page_range = range(max(1, rmas.number - 2), min(paginator.num_pages + 1, rmas.number + 3))
    except PageNotAnInteger:
        rmas = paginator.page(1)
        page_range = range(1, min(paginator.num_pages + 1, 6))
    except EmptyPage:
        rmas = paginator.page(paginator.num_pages)
        page_range = range(max(1, paginator.num_pages - 4), paginator.num_pages + 1)

    context = {
        'rmas': rmas,
        'page_range': page_range,
        'form': form,
    }

    return render(request, 'rma/rma_list.html', context)


@login_required
@permission_required('rma', 'view')
def rma_detail(request, pk):
    """Show details for a specific RMA."""
    rma = get_object_or_404(
        RMA.objects.select_related('supplier', 'rma_warehouse', 'created_by', 'approved_by')
        .prefetch_related('items__product', 'history', 'comments'),
        pk=pk
    )

    # Group items by resolution
    resolved_items = []
    unresolved_items = []

    for item in rma.items.all():
        if item.is_resolved:
            resolved_items.append(item)
        else:
            unresolved_items.append(item)

    # Status update form
    status_form = RMAStatusUpdateForm(current_status=rma.status)

    # Resolution form
    resolution_form = RMAResolutionForm()

    # Comment form
    comment_form = RMACommentForm()

    # Recent comments
    recent_comments = rma.comments.select_related('user').order_by('-created_at')[:5]

    # Recent history
    recent_history = rma.history.select_related('changed_by').order_by('-timestamp')[:5]

    # Has resolution been set
    has_resolution = rma.resolution_type is not None

    # Check if there are RMA forms for this supplier
    has_supplier_forms = False
    # This would connect to some document templates in the future

    # Check user permissions
    can_edit = request.user.has_perm('rma.edit') and rma.status in [RMAStatus.DRAFT]
    can_approve = request.user.has_perm('rma.approve') and rma.status == RMAStatus.PENDING
    can_resolve = request.user.has_perm('rma.edit') and rma.status in [RMAStatus.SENT, RMAStatus.APPROVED]

    # Forms for changing RMA status
    if request.method == 'POST':
        action = request.POST.get('action')

        # Handle different actions
        if action == 'update_status':
            status_form = RMAStatusUpdateForm(request.POST, current_status=rma.status)
            if status_form.is_valid():
                new_status = status_form.cleaned_data['status']
                reason = status_form.cleaned_data.get('reason', '')

                try:
                    if new_status == RMAStatus.PENDING and rma.status == RMAStatus.DRAFT:
                        rma.submit(request.user)
                        messages.success(request, f'RMA {rma.rma_number} wurde zur Bearbeitung eingereicht.')
                    elif new_status == RMAStatus.APPROVED and rma.status == RMAStatus.PENDING:
                        rma.approve(request.user)
                        messages.success(request, f'RMA {rma.rma_number} wurde genehmigt.')
                    elif new_status == RMAStatus.SENT and rma.status == RMAStatus.APPROVED:
                        tracking = request.POST.get('tracking_number', '')
                        shipping_date_str = request.POST.get('shipping_date')
                        shipping_date = None
                        if shipping_date_str:
                            try:
                                from datetime import datetime
                                shipping_date = datetime.strptime(shipping_date_str, '%Y-%m-%d').date()
                            except:
                                pass

                        rma.mark_sent(request.user, tracking, shipping_date)
                        messages.success(request, f'RMA {rma.rma_number} wurde als versendet markiert.')
                    elif new_status == RMAStatus.REJECTED and rma.status == RMAStatus.PENDING:
                        rma.reject(request.user, reason)
                        messages.warning(request, f'RMA {rma.rma_number} wurde abgelehnt.')
                    elif new_status == RMAStatus.CANCELLED:
                        rma.cancel(request.user, reason)
                        messages.warning(request, f'RMA {rma.rma_number} wurde storniert.')
                    elif new_status == RMAStatus.DRAFT and rma.status == RMAStatus.REJECTED:
                        rma.update_status(RMAStatus.DRAFT, request.user)
                        messages.success(request, f'RMA {rma.rma_number} wurde zurück in den Entwurfsstatus gesetzt.')
                    else:
                        messages.error(request, f'Ungültiger Statuswechsel.')

                except ValueError as e:
                    messages.error(request, str(e))

                return redirect('rma_detail', pk=rma.pk)

        # Handle resolution
        elif action == 'resolve':
            resolution_form = RMAResolutionForm(request.POST)
            if resolution_form.is_valid():
                resolution_type = resolution_form.cleaned_data['resolution_type']
                resolution_notes = resolution_form.cleaned_data['resolution_notes']

                try:
                    rma.resolve(request.user, resolution_type, resolution_notes)
                    messages.success(request, f'RMA {rma.rma_number} wurde als erledigt markiert.')

                    # Handle additional resolution data
                    if resolution_type == RMAResolutionType.REPLACEMENT and resolution_form.cleaned_data.get(
                            'received_replacement'):
                        # Create history entry for replacement received
                        RMAHistory.objects.create(
                            rma=rma,
                            changed_by=request.user,
                            note=f"Ersatz erhalten am {resolution_form.cleaned_data.get('replacement_date')}"
                        )

                    elif resolution_type == RMAResolutionType.REFUND:
                        # Create history entry for refund
                        refund_amount = resolution_form.cleaned_data.get('refund_amount')
                        refund_date = resolution_form.cleaned_data.get('refund_date')

                        if refund_amount and refund_date:
                            RMAHistory.objects.create(
                                rma=rma,
                                changed_by=request.user,
                                note=f"Rückerstattung von {refund_amount} € erhalten am {refund_date}"
                            )

                    return redirect('rma_detail', pk=rma.pk)

                except ValueError as e:
                    messages.error(request, str(e))

        # Handle comments
        elif action == 'add_comment':
            comment_form = RMACommentForm(request.POST, request.FILES)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.rma = rma
                comment.user = request.user
                comment.save()

                messages.success(request, 'Kommentar wurde hinzugefügt.')
                return redirect('rma_detail', pk=rma.pk)

    context = {
        'rma': rma,
        'resolved_items': resolved_items,
        'unresolved_items': unresolved_items,
        'status_form': status_form,
        'resolution_form': resolution_form,
        'comment_form': comment_form,
        'recent_comments': recent_comments,
        'recent_history': recent_history,
        'has_resolution': has_resolution,
        'has_supplier_forms': has_supplier_forms,
        'can_edit': can_edit,
        'can_approve': can_approve,
        'can_resolve': can_resolve,
    }

    return render(request, 'rma/rma_detail.html', context)


@login_required
@permission_required('rma', 'create')
def rma_create(request):
    """Create a new RMA."""
    # Check for optional receipt_item_id to pre-fill the form
    receipt_item_id = request.GET.get('receipt_item_id')
    purchase_order_id = request.GET.get('purchase_order_id')

    purchase_order = None
    if purchase_order_id:
        try:
            purchase_order = PurchaseOrder.objects.get(pk=purchase_order_id)
        except PurchaseOrder.DoesNotExist:
            pass

    if request.method == 'POST':
        form = RMAForm(request.POST, user=request.user, receipt_item_id=receipt_item_id, purchase_order=purchase_order)

        if form.is_valid():
            with transaction.atomic():
                # Create RMA with a generated RMA number
                rma = form.save(commit=False)
                rma.rma_number = generate_rma_number()
                rma.created_by = request.user
                rma.save()

                # Create initial history entry
                RMAHistory.objects.create(
                    rma=rma,
                    changed_by=request.user,
                    note="RMA erstellt"
                )

                messages.success(request, f'RMA {rma.rma_number} wurde erfolgreich erstellt.')

                # If receipt_item_id was provided, redirect to add this item to the RMA
                if receipt_item_id:
                    return redirect('rma_add_item', pk=rma.pk, receipt_item_id=receipt_item_id)

                return redirect('rma_detail', pk=rma.pk)
    else:
        form = RMAForm(user=request.user, receipt_item_id=receipt_item_id, purchase_order=purchase_order)

    context = {
        'form': form,
        'is_new': True,
    }

    return render(request, 'rma/rma_form.html', context)


@login_required
@permission_required('rma', 'edit')
def rma_update(request, pk):
    """Update an existing RMA."""
    rma = get_object_or_404(RMA, pk=pk)

    # Only allow editing if RMA is in draft status
    if rma.status != RMAStatus.DRAFT:
        messages.error(request,
                       f'RMA {rma.rma_number} kann nicht bearbeitet werden, da sie nicht im Entwurfsstatus ist.')
        return redirect('rma_detail', pk=rma.pk)

    if request.method == 'POST':
        form = RMAForm(request.POST, instance=rma, user=request.user)

        if form.is_valid():
            form.save()

            # Create history entry
            RMAHistory.objects.create(
                rma=rma,
                changed_by=request.user,
                note="RMA Informationen aktualisiert"
            )

            messages.success(request, f'RMA {rma.rma_number} wurde erfolgreich aktualisiert.')
            return redirect('rma_detail', pk=rma.pk)
    else:
        form = RMAForm(instance=rma, user=request.user)

    context = {
        'form': form,
        'rma': rma,
        'is_new': False,
    }

    return render(request, 'rma/rma_form.html', context)


@login_required
@permission_required('rma', 'edit')
def rma_add_item(request, pk, receipt_item_id=None):
    """Add an item to an RMA."""
    rma = get_object_or_404(RMA, pk=pk)

    # Only allow adding items if RMA is in draft status
    if rma.status != RMAStatus.DRAFT:
        messages.error(request,
                       f'Es können keine Positionen hinzugefügt werden, da die RMA nicht im Entwurfsstatus ist.')
        return redirect('rma_detail', pk=rma.pk)

    if request.method == 'POST':
        form = RMAItemForm(request.POST, rma=rma, receipt_item_id=receipt_item_id)

        if form.is_valid():
            item = form.save(commit=False)
            item.rma = rma
            item.save()

            # Update total value
            rma.update_total_value()

            # Create history entry
            product_name = item.product.name
            product_qty = f"{item.quantity} {item.product.unit}"
            RMAHistory.objects.create(
                rma=rma,
                changed_by=request.user,
                note=f"Position hinzugefügt: {product_name} ({product_qty})"
            )

            # Move item to RMA warehouse if receipt_item is provided
            if item.receipt_item:
                try:
                    with transaction.atomic():
                        # Create stock movement to adjust warehouse stock
                        original_warehouse = item.receipt_item.warehouse

                        # First, remove from original warehouse
                        StockMovement.objects.create(
                            product=item.product,
                            warehouse=original_warehouse,
                            quantity=-item.quantity,  # Negative = removal
                            movement_type='adj',
                            reference=f"RMA: {rma.rma_number}",
                            notes=f"Defekte Artikel zur RMA transferiert",
                            created_by=request.user
                        )

                        # Update product warehouse quantity
                        from core.models import ProductWarehouse
                        product_warehouse, created = ProductWarehouse.objects.get_or_create(
                            product=item.product,
                            warehouse=original_warehouse,
                            defaults={'quantity': 0}
                        )

                        # Ensure we don't go below zero
                        if product_warehouse.quantity >= item.quantity:
                            product_warehouse.quantity -= item.quantity
                            product_warehouse.save()

                        # Then, add to RMA warehouse
                        StockMovement.objects.create(
                            product=item.product,
                            warehouse=rma.rma_warehouse,
                            quantity=item.quantity,  # Positive = addition
                            movement_type='in',
                            reference=f"RMA: {rma.rma_number}",
                            notes=f"Defekte Artikel im RMA-Lager aufgenommen",
                            created_by=request.user
                        )

                        # Update RMA warehouse quantity
                        rma_product_warehouse, created = ProductWarehouse.objects.get_or_create(
                            product=item.product,
                            warehouse=rma.rma_warehouse,
                            defaults={'quantity': 0}
                        )

                        rma_product_warehouse.quantity += item.quantity
                        rma_product_warehouse.save()

                        messages.success(request,
                                         f"{item.quantity} {item.product.unit} von {item.product.name} wurden ins RMA-Lager übertragen.")

                except Exception as e:
                    messages.error(request, f"Fehler beim Übertragen der Artikel ins RMA-Lager: {str(e)}")

            messages.success(request, f'Position wurde erfolgreich zur RMA hinzugefügt.')

            # Check if user wants to add another item
            if 'add_another' in request.POST:
                return redirect('rma_add_item', pk=rma.pk)

            return redirect('rma_detail', pk=rma.pk)
    else:
        form = RMAItemForm(rma=rma, receipt_item_id=receipt_item_id)

    context = {
        'form': form,
        'rma': rma,
    }

    return render(request, 'rma/rma_item_form.html', context)


@login_required
@permission_required('rma', 'edit')
def rma_edit_item(request, pk, item_id):
    """Edit an existing RMA item."""
    rma = get_object_or_404(RMA, pk=pk)
    item = get_object_or_404(RMAItem, pk=item_id, rma=rma)

    # Only allow editing if RMA is in draft status
    if rma.status != RMAStatus.DRAFT:
        messages.error(request, f'Position kann nicht bearbeitet werden, da die RMA nicht im Entwurfsstatus ist.')
        return redirect('rma_detail', pk=rma.pk)

    if request.method == 'POST':
        form = RMAItemForm(request.POST, instance=item, rma=rma)

        if form.is_valid():
            # Save the original quantity to calculate the difference
            original_qty = item.quantity

            # Save the form
            form.save()

            # If quantity changed, adjust stock movement
            if item.quantity != original_qty:
                # Calculate difference
                qty_diff = item.quantity - original_qty

                try:
                    # Adjust RMA warehouse quantity
                    StockMovement.objects.create(
                        product=item.product,
                        warehouse=rma.rma_warehouse,
                        quantity=qty_diff,
                        movement_type='adj',
                        reference=f"RMA: {rma.rma_number}",
                        notes=f"Mengenanpassung von {original_qty} auf {item.quantity}",
                        created_by=request.user
                    )

                    # Update product warehouse quantity
                    from core.models import ProductWarehouse
                    product_warehouse, created = ProductWarehouse.objects.get_or_create(
                        product=item.product,
                        warehouse=rma.rma_warehouse,
                        defaults={'quantity': 0}
                    )

                    product_warehouse.quantity += qty_diff
                    product_warehouse.save()

                except Exception as e:
                    messages.error(request, f"Fehler bei der Lageranpassung: {str(e)}")

            # Update total value
            rma.update_total_value()

            # Create history entry
            RMAHistory.objects.create(
                rma=rma,
                changed_by=request.user,
                note=f"Position bearbeitet: {item.product.name}"
            )

            messages.success(request, f'Position wurde erfolgreich aktualisiert.')
            return redirect('rma_detail', pk=rma.pk)
    else:
        form = RMAItemForm(instance=item, rma=rma)

    context = {
        'form': form,
        'rma': rma,
        'item': item,
    }

    return render(request, 'rma/rma_item_form.html', context)


@login_required
@permission_required('rma', 'delete')
def rma_delete_item(request, pk, item_id):
    """Delete an item from an RMA."""
    rma = get_object_or_404(RMA, pk=pk)
    item = get_object_or_404(RMAItem, pk=item_id, rma=rma)

    # Only allow deleting if RMA is in draft status
    if rma.status != RMAStatus.DRAFT:
        messages.error(request, f'Position kann nicht gelöscht werden, da die RMA nicht im Entwurfsstatus ist.')
        return redirect('rma_detail', pk=rma.pk)

    if request.method == 'POST':
        # First, adjust the stock in RMA warehouse
        try:
            StockMovement.objects.create(
                product=item.product,
                warehouse=rma.rma_warehouse,
                quantity=-item.quantity,  # Negative = removal
                movement_type='adj',
                reference=f"RMA: {rma.rma_number}",
                notes=f"Position aus RMA entfernt",
                created_by=request.user
            )

            # Update RMA warehouse quantity
            from core.models import ProductWarehouse
            product_warehouse, created = ProductWarehouse.objects.get_or_create(
                product=item.product,
                warehouse=rma.rma_warehouse,
                defaults={'quantity': 0}
            )

            # Ensure we don't go below zero
            if product_warehouse.quantity >= item.quantity:
                product_warehouse.quantity -= item.quantity
                product_warehouse.save()

            # Prompt user if they want to move the item back to original warehouse
            return_to_origin = request.POST.get('return_to_origin') == 'yes'

            if return_to_origin and item.receipt_item:
                original_warehouse = item.receipt_item.warehouse

                # Add back to original warehouse
                StockMovement.objects.create(
                    product=item.product,
                    warehouse=original_warehouse,
                    quantity=item.quantity,
                    movement_type='in',
                    reference=f"RMA: {rma.rma_number}",
                    notes=f"Artikel von RMA zurück ins Lager",
                    created_by=request.user
                )

                # Update original warehouse quantity
                orig_product_warehouse, created = ProductWarehouse.objects.get_or_create(
                    product=item.product,
                    warehouse=original_warehouse,
                    defaults={'quantity': 0}
                )

                orig_product_warehouse.quantity += item.quantity
                orig_product_warehouse.save()

                messages.info(request,
                              f"{item.quantity} {item.product.unit} von {item.product.name} wurden ins ursprüngliche Lager zurücktransferiert.")

        except Exception as e:
            messages.error(request, f"Fehler bei der Lageranpassung: {str(e)}")

        # Create history entry
        product_name = item.product.name
        product_qty = f"{item.quantity} {item.product.unit}"
        RMAHistory.objects.create(
            rma=rma,
            changed_by=request.user,
            note=f"Position entfernt: {product_name} ({product_qty})"
        )

        # Delete the item
        item.delete()

        # Update total value
        rma.update_total_value()

        messages.success(request, f'Position wurde erfolgreich aus der RMA entfernt.')
        return redirect('rma_detail', pk=rma.pk)

    context = {
        'rma': rma,
        'item': item,
    }

    return render(request, 'rma/rma_item_delete.html', context)


@login_required
@permission_required('rma', 'delete')
def rma_delete(request, pk):
    """Delete an RMA."""
    rma = get_object_or_404(RMA, pk=pk)

    # Only allow deleting if RMA is in draft status
    if rma.status != RMAStatus.DRAFT:
        messages.error(request, f'RMA {rma.rma_number} kann nicht gelöscht werden, da sie nicht im Entwurfsstatus ist.')
        return redirect('rma_detail', pk=rma.pk)

    if request.method == 'POST':
        # First, handle stock in RMA warehouse
        try:
            for item in rma.items.all():
                # Remove from RMA warehouse
                StockMovement.objects.create(
                    product=item.product,
                    warehouse=rma.rma_warehouse,
                    quantity=-item.quantity,  # Negative = removal
                    movement_type='adj',
                    reference=f"RMA: {rma.rma_number}",
                    notes=f"RMA wurde gelöscht",
                    created_by=request.user
                )

                # Update RMA warehouse quantity
                from core.models import ProductWarehouse
                product_warehouse, created = ProductWarehouse.objects.get_or_create(
                    product=item.product,
                    warehouse=rma.rma_warehouse,
                    defaults={'quantity': 0}
                )

                # Ensure we don't go below zero
                if product_warehouse.quantity >= item.quantity:
                    product_warehouse.quantity -= item.quantity
                    product_warehouse.save()

                # Check if user wants to return items to original warehouse
                return_to_origin = request.POST.get('return_to_origin') == 'yes'

                if return_to_origin and item.receipt_item:
                    original_warehouse = item.receipt_item.warehouse

                    # Add back to original warehouse
                    StockMovement.objects.create(
                        product=item.product,
                        warehouse=original_warehouse,
                        quantity=item.quantity,
                        movement_type='in',
                        reference=f"RMA: {rma.rma_number}",
                        notes=f"Artikel von gelöschter RMA zurück ins Lager",
                        created_by=request.user
                    )

                    # Update original warehouse quantity
                    orig_product_warehouse, created = ProductWarehouse.objects.get_or_create(
                        product=item.product,
                        warehouse=original_warehouse,
                        defaults={'quantity': 0}
                    )

                    orig_product_warehouse.quantity += item.quantity
                    orig_product_warehouse.save()

        except Exception as e:
            messages.error(request, f"Fehler bei der Lageranpassung: {str(e)}")

        # Store RMA number for message
        rma_number = rma.rma_number

        # Delete the RMA
        rma.delete()

        messages.success(request, f'RMA {rma_number} wurde erfolgreich gelöscht.')
        return redirect('rma_list')

    context = {
        'rma': rma,
    }

    return render(request, 'rma/rma_delete.html', context)


@login_required
@permission_required('rma', 'edit')
def rma_toggle_item_resolved(request, pk, item_id):
    """Toggle the resolved status of an RMA item."""
    rma = get_object_or_404(RMA, pk=pk)
    item = get_object_or_404(RMAItem, pk=item_id, rma=rma)

    # Only allow resolving items for approved, sent or resolved RMAs
    if rma.status not in [RMAStatus.APPROVED, RMAStatus.SENT, RMAStatus.RESOLVED]:
        messages.error(request,
                       f'Der Status dieser Position kann nicht geändert werden, da die RMA im Status {rma.get_status_display()} ist.')
        return redirect('rma_detail', pk=rma.pk)

    if request.method == 'POST':
        # Toggle resolved status
        item.is_resolved = not item.is_resolved

        # If resolving, add notes
        if item.is_resolved:
            resolution_notes = request.POST.get('resolution_notes', '')
            item.resolution_notes = resolution_notes

        item.save()

        # Create history entry
        status = "erledigt" if item.is_resolved else "offen"
        RMAHistory.objects.create(
            rma=rma,
            changed_by=request.user,
            note=f"Position {item.product.name} als {status} markiert."
        )

        messages.success(request, f'Position {item.product.name} wurde als {status} markiert.')

        # Check if all items are resolved, and if so, prompt to mark entire RMA as resolved
        if rma.status != RMAStatus.RESOLVED and rma.items.filter(is_resolved=False).count() == 0:
            messages.info(request,
                          'Alle Positionen sind als erledigt markiert. Sie können jetzt die gesamte RMA als erledigt markieren.')

        return redirect('rma_detail', pk=rma.pk)

    context = {
        'rma': rma,
        'item': item,
    }

    return render(request, 'rma/rma_toggle_item_resolved.html', context)


@login_required
@permission_required('rma', 'edit')
def rma_add_photos(request, pk, item_id):
    """Add photos to an RMA item."""
    rma = get_object_or_404(RMA, pk=pk)
    item = get_object_or_404(RMAItem, pk=item_id, rma=rma)

    # Only allow adding photos for draft or pending RMAs
    if rma.status not in [RMAStatus.DRAFT, RMAStatus.PENDING]:
        messages.error(request, f'Photos können nicht hinzugefügt werden, da die RMA nicht im Entwurfsstatus ist.')
        return redirect('rma_detail', pk=rma.pk)

    if request.method == 'POST':
        photos = request.FILES.getlist('photos')
        captions = request.POST.getlist('captions')

        if not photos:
            messages.error(request, 'Bitte wählen Sie mindestens ein Foto aus.')
            return redirect('rma_add_photos', pk=rma.pk, item_id=item.pk)

        # Process each photo
        for i, photo in enumerate(photos):
            caption = captions[i] if i < len(captions) else ''

            RMAPhoto.objects.create(
                rma_item=item,
                image=photo,
                caption=caption
            )

        # Update has_photos flag
        item.has_photos = True
        item.save()

        # Create history entry
        RMAHistory.objects.create(
            rma=rma,
            changed_by=request.user,
            note=f"{len(photos)} Foto(s) zur Position {item.product.name} hinzugefügt."
        )

        messages.success(request, f'{len(photos)} Foto(s) wurden erfolgreich zur Position hinzugefügt.')
        return redirect('rma_detail', pk=rma.pk)

    # Get existing photos
    photos = item.photos.all()

    context = {
        'rma': rma,
        'item': item,
        'photos': photos,
    }

    return render(request, 'rma/rma_add_photos.html', context)


@login_required
@permission_required('rma', 'edit')
def rma_delete_photo(request, pk, item_id, photo_id):
    """Delete a photo from an RMA item."""
    rma = get_object_or_404(RMA, pk=pk)
    item = get_object_or_404(RMAItem, pk=item_id, rma=rma)
    photo = get_object_or_404(RMAPhoto, pk=photo_id, rma_item=item)

    # Only allow deleting photos for draft or pending RMAs
    if rma.status not in [RMAStatus.DRAFT, RMAStatus.PENDING]:
        messages.error(request, f'Photos können nicht gelöscht werden, da die RMA nicht im Entwurfsstatus ist.')
        return redirect('rma_detail', pk=rma.pk)

    if request.method == 'POST':
        photo.delete()

        # Update has_photos flag if no photos remain
        if not item.photos.exists():
            item.has_photos = False
            item.save()

        # Create history entry
        RMAHistory.objects.create(
            rma=rma,
            changed_by=request.user,
            note=f"Foto von Position {item.product.name} gelöscht."
        )

        messages.success(request, f'Foto wurde erfolgreich gelöscht.')
        return redirect('rma_add_photos', pk=rma.pk, item_id=item.pk)

    context = {
        'rma': rma,
        'item': item,
        'photo': photo,
    }

    return render(request, 'rma/rma_delete_photo.html', context)


@login_required
@permission_required('rma', 'edit')
def rma_add_document(request, pk):
    """Add a document to an RMA."""
    rma = get_object_or_404(RMA, pk=pk)

    if request.method == 'POST':
        document_type = request.POST.get('document_type')
        title = request.POST.get('title')
        notes = request.POST.get('notes', '')
        file = request.FILES.get('file')

        if not document_type or not title or not file:
            messages.error(request, 'Bitte füllen Sie alle erforderlichen Felder aus.')
            return redirect('rma_add_document', pk=rma.pk)

        # Create document
        RMADocument.objects.create(
            rma=rma,
            document_type=document_type,
            title=title,
            notes=notes,
            file=file,
            uploaded_by=request.user
        )

        # Create history entry
        RMAHistory.objects.create(
            rma=rma,
            changed_by=request.user,
            note=f"Dokument '{title}' hinzugefügt."
        )

        messages.success(request, f'Dokument wurde erfolgreich hinzugefügt.')
        return redirect('rma_detail', pk=rma.pk)

    context = {
        'rma': rma,
    }

    return render(request, 'rma/rma_add_document.html', context)


@login_required
@permission_required('rma', 'delete')
def rma_delete_document(request, pk, document_id):
    """Delete a document from an RMA."""
    rma = get_object_or_404(RMA, pk=pk)
    document = get_object_or_404(RMADocument, pk=document_id, rma=rma)

    if request.method == 'POST':
        document_title = document.title
        document.delete()

        # Create history entry
        RMAHistory.objects.create(
            rma=rma,
            changed_by=request.user,
            note=f"Dokument '{document_title}' gelöscht."
        )

        messages.success(request, f'Dokument wurde erfolgreich gelöscht.')
        return redirect('rma_detail', pk=rma.pk)

    context = {
        'rma': rma,
        'document': document,
    }

    return render(request, 'rma/rma_delete_document.html', context)


@login_required
@permission_required('rma', 'delete')
def rma_delete_comment(request, pk, comment_id):
    """Delete a comment from an RMA."""
    rma = get_object_or_404(RMA, pk=pk)
    comment = get_object_or_404(RMAComment, pk=comment_id, rma=rma)

    # Only allow users to delete their own comments or users with admin permission
    if comment.user != request.user and not request.user.has_perm('rma.admin'):
        messages.error(request, f'Sie haben keine Berechtigung, diesen Kommentar zu löschen.')
        return redirect('rma_detail', pk=rma.pk)

    if request.method == 'POST':
        comment.delete()

        messages.success(request, f'Kommentar wurde erfolgreich gelöscht.')
        return redirect('rma_detail', pk=rma.pk)

    context = {
        'rma': rma,
        'comment': comment,
    }

    return render(request, 'rma/rma_delete_comment.html', context)


@login_required
@permission_required('rma', 'view')
def rma_history(request, pk):
    """View the complete history of an RMA."""
    rma = get_object_or_404(RMA, pk=pk)

    # Get all history entries
    history = rma.history.select_related('changed_by').order_by('-timestamp')

    context = {
        'rma': rma,
        'history': history,
    }

    return render(request, 'rma/rma_history.html', context)


@login_required
@permission_required('rma', 'view')
def rma_comments(request, pk):
    """View all comments for an RMA."""
    rma = get_object_or_404(RMA, pk=pk)

    # Get all comments
    comments = rma.comments.select_related('user').order_by('-created_at')

    context = {
        'rma': rma,
        'comments': comments,
    }

    return render(request, 'rma/rma_comments.html', context)


@login_required
@permission_required('rma', 'view')
def rma_print(request, pk):
    """Generate a printable view of an RMA."""
    rma = get_object_or_404(
        RMA.objects.select_related('supplier', 'rma_warehouse', 'created_by')
        .prefetch_related('items__product'),
        pk=pk
    )

    context = {
        'rma': rma,
        'print_mode': True,
    }

    return render(request, 'rma/rma_print.html', context)


@login_required
def get_receipt_item_details(request):
    """AJAX endpoint to get details for a receipt item."""
    receipt_item_id = request.GET.get('receipt_item_id')

    if not receipt_item_id:
        return JsonResponse({'success': False, 'message': 'Receipt item ID is required'})

    try:
        receipt_item = PurchaseOrderReceiptItem.objects.select_related(
            'order_item__product',
            'order_item__purchase_order__supplier',
            'warehouse'
        ).get(pk=receipt_item_id)

        return JsonResponse({
            'success': True,
            'product_id': receipt_item.order_item.product.id,
            'product_name': receipt_item.order_item.product.name,
            'product_sku': receipt_item.order_item.product.sku,
            'quantity': float(receipt_item.quantity_received),
            'unit': receipt_item.order_item.product.unit,
            'unit_price': float(receipt_item.order_item.unit_price),
            'supplier_id': receipt_item.order_item.purchase_order.supplier.id,
            'supplier_name': receipt_item.order_item.purchase_order.supplier.name,
            'warehouse_id': receipt_item.warehouse.id,
            'warehouse_name': receipt_item.warehouse.name,
            'batch_number': receipt_item.batch_number or '',
            'expiry_date': receipt_item.expiry_date.isoformat() if receipt_item.expiry_date else '',
            'order_id': receipt_item.order_item.purchase_order.id,
            'order_number': receipt_item.order_item.purchase_order.order_number,
        })

    except PurchaseOrderReceiptItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Receipt item not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# Add this to rma/views.py

@login_required
@permission_required('rma', 'create')
def rma_create_from_receipt(request, order_id, receipt_id):
    """Create an RMA from receipt items marked as defective."""
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    receipt = get_object_or_404(PurchaseOrderReceipt, pk=receipt_id, purchase_order=order)

    # Get defective items from session
    defective_items = request.session.get('defective_items', [])

    if not defective_items:
        messages.error(request, 'Keine mangelhaften Artikel gefunden. Bitte wählen Sie zunächst defekte Artikel aus.')
        return redirect('purchase_order_detail', pk=order.id)

    if request.method == 'POST':
        form = RMAForm(request.POST, user=request.user, purchase_order=order)

        if form.is_valid():
            with transaction.atomic():
                # Create RMA with a generated RMA number
                rma = form.save(commit=False)
                rma.rma_number = generate_rma_number()
                rma.created_by = request.user
                rma.save()

                # Create initial history entry
                RMAHistory.objects.create(
                    rma=rma,
                    changed_by=request.user,
                    note="RMA erstellt aus Wareneingang"
                )

                # Process defective items
                receipt_items = {}
                for item_data in defective_items:
                    receipt_item_id = item_data.get('receipt_item_id')

                    try:
                        receipt_item = PurchaseOrderReceiptItem.objects.get(pk=receipt_item_id)
                        receipt_items[receipt_item_id] = receipt_item

                        # Convert quantity back to Decimal
                        quantity = Decimal(item_data.get('quantity', '0'))
                        issue_type = item_data.get('issue_type', 'defective')
                        issue_description = item_data.get('issue_description', '')

                        # Create RMA item
                        rma_item = RMAItem.objects.create(
                            rma=rma,
                            product=receipt_item.order_item.product,
                            receipt_item=receipt_item,
                            quantity=quantity,
                            unit_price=receipt_item.order_item.unit_price,
                            issue_type=issue_type,
                            issue_description=issue_description,
                            batch_number=receipt_item.batch_number,
                            expiry_date=receipt_item.expiry_date
                        )

                        # Transfer to RMA warehouse
                        try:
                            # First, remove from original warehouse
                            StockMovement.objects.create(
                                product=rma_item.product,
                                warehouse=receipt_item.warehouse,
                                quantity=-quantity,  # Negative = removal
                                movement_type='adj',
                                reference=f"RMA: {rma.rma_number}",
                                notes=f"Defekte Artikel zur RMA transferiert",
                                created_by=request.user
                            )

                            # Update product warehouse quantity
                            from core.models import ProductWarehouse
                            product_warehouse, created = ProductWarehouse.objects.get_or_create(
                                product=rma_item.product,
                                warehouse=receipt_item.warehouse,
                                defaults={'quantity': 0}
                            )

                            # Ensure we don't go below zero
                            if product_warehouse.quantity >= quantity:
                                product_warehouse.quantity -= quantity
                                product_warehouse.save()

                            # Then, add to RMA warehouse
                            StockMovement.objects.create(
                                product=rma_item.product,
                                warehouse=rma.rma_warehouse,
                                quantity=quantity,  # Positive = addition
                                movement_type='in',
                                reference=f"RMA: {rma.rma_number}",
                                notes=f"Defekte Artikel im RMA-Lager aufgenommen",
                                created_by=request.user
                            )

                            # Update RMA warehouse quantity
                            rma_product_warehouse, created = ProductWarehouse.objects.get_or_create(
                                product=rma_item.product,
                                warehouse=rma.rma_warehouse,
                                defaults={'quantity': 0}
                            )

                            rma_product_warehouse.quantity += quantity
                            rma_product_warehouse.save()

                        except Exception as e:
                            messages.error(request, f"Fehler beim Übertragen der Artikel ins RMA-Lager: {str(e)}")

                    except PurchaseOrderReceiptItem.DoesNotExist:
                        messages.warning(request, f'Wareneingansposition {receipt_item_id} nicht gefunden.')

                # Update total value
                rma.update_total_value()

                # Clear session data
                if 'defective_items' in request.session:
                    del request.session['defective_items']

                messages.success(request,
                                 f'RMA {rma.rma_number} wurde erfolgreich erstellt mit {rma.items.count()} Positionen.')
                return redirect('rma_detail', pk=rma.pk)
    else:
        # Pre-fill the form with order details
        form = RMAForm(user=request.user, purchase_order=order)

        # Set some default values
        try:
            # Try to find a warehouse with "RMA" in the name
            from inventory.models import Warehouse
            rma_warehouses = Warehouse.objects.filter(is_active=True, name__icontains='RMA')
            if rma_warehouses.exists():
                form.fields['rma_warehouse'].initial = rma_warehouses.first().pk
        except:
            pass

    # Prepare preview of items to be added
    preview_items = []
    for item_data in defective_items:
        receipt_item_id = item_data.get('receipt_item_id')
        try:
            receipt_item = PurchaseOrderReceiptItem.objects.get(pk=receipt_item_id)

            preview_items.append({
                'product': receipt_item.order_item.product,
                'quantity': Decimal(item_data.get('quantity', '0')),
                'unit_price': receipt_item.order_item.unit_price,
                'issue_type': item_data.get('issue_type', 'defective'),
                'issue_type_display': dict(RMAIssueType.choices)[item_data.get('issue_type', 'defective')],
                'issue_description': item_data.get('issue_description', ''),
                'batch_number': receipt_item.batch_number,
                'expiry_date': receipt_item.expiry_date,
                'value': Decimal(item_data.get('quantity', '0')) * receipt_item.order_item.unit_price
            })
        except (PurchaseOrderReceiptItem.DoesNotExist, InvalidOperation):
            pass

    context = {
        'form': form,
        'is_new': True,
        'order': order,
        'receipt': receipt,
        'preview_items': preview_items,
        'from_receipt': True  # Flag to indicate this is coming from a receipt
    }

    return render(request, 'rma/rma_create_from_receipt.html', context)