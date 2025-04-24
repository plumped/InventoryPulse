"""
Views related to stock takes in the inventory app.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404

from accessmanagement.models import WarehouseAccess
from core.utils.pagination import paginate_queryset
from ..forms import StockTakeFilterForm
from ..models import Warehouse
from ..services.stock_take_service import StockTakeService
from ..services.warehouse_service import WarehouseService


@login_required
@permission_required('inventory.view_stocktake', raise_exception=True)
def stock_take_list(request):
    """List all stock takes with filtering."""
    # Initialize services
    stock_take_service = StockTakeService()
    warehouse_service = WarehouseService()

    # Nur Inventuren in Lagern anzeigen, auf die der Benutzer Zugriff hat
    if request.user.is_superuser:
        accessible_warehouses = warehouse_service.get_active_warehouses()
    else:
        accessible_warehouses = [w for w in warehouse_service.get_active_warehouses()
                                 if WarehouseAccess.has_access(request.user, w, 'view')]

    # Get filter parameters
    warehouse_id = request.GET.get('warehouse', '')

    # Check warehouse access if warehouse_id is provided
    if warehouse_id:
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
        if not request.user.is_superuser and not WarehouseAccess.has_access(request.user, warehouse, 'view'):
            messages.error(request, "Sie haben keinen Zugriff auf dieses Lager.")
            warehouse_id = None

    # Filter Form
    filter_form = StockTakeFilterForm(request.GET or None)

    # Prepare filter parameters
    filters = {}
    if warehouse_id:
        filters['warehouse_id'] = warehouse_id

    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        inventory_type = filter_form.cleaned_data.get('inventory_type')
        date_from = filter_form.cleaned_data.get('date_from')
        date_to = filter_form.cleaned_data.get('date_to')
        search = filter_form.cleaned_data.get('search')

        if status:
            filters['status'] = status
        if inventory_type:
            filters['inventory_type'] = inventory_type
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        if search:
            filters['search_query'] = search

    # Get stock takes with filters
    stock_takes_list = stock_take_service.get_stock_takes(**filters)

    # Filter by accessible warehouses
    if not request.user.is_superuser:
        stock_takes_list = stock_takes_list.filter(warehouse__in=accessible_warehouses)

    # Paginierung
    stock_takes = paginate_queryset(stock_takes_list, request.GET.get('page'), per_page=10)

    context = {
        'stock_takes': stock_takes,
        'filter_form': filter_form,
        'warehouses': accessible_warehouses,
        'warehouse_id': warehouse_id,
    }

    return render(request, 'inventory/stock_take_list.html', context)


@login_required
@permission_required('inventory.add_stocktake', raise_exception=True)
def stock_take_create(request):
    """Create a new stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.view_stocktake', raise_exception=True)
def stock_take_detail(request, pk):
    """View details of a stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.change_stocktake', raise_exception=True)
def stock_take_update(request, pk):
    """Update a stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.delete_stocktake', raise_exception=True)
def stock_take_delete(request, pk):
    """Delete a stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.change_stocktake', raise_exception=True)
def stock_take_start(request, pk):
    """Start a stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.change_stocktake', raise_exception=True)
def stock_take_complete(request, pk):
    """Complete a stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.change_stocktake', raise_exception=True)
def stock_take_cancel(request, pk):
    """Cancel a stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.change_stocktakeitem', raise_exception=True)
def stock_take_item_count(request, pk, item_id):
    """Count an item in a stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.change_stocktakeitem', raise_exception=True)
def stock_take_count_items(request, pk):
    """Count items in a stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.change_stocktakeitem', raise_exception=True)
def stock_take_barcode_scan(request, pk):
    """Scan barcodes for a stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.view_stocktake', raise_exception=True)
def stock_take_report(request, pk):
    """Generate a report for a stock take."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.view_stocktake', raise_exception=True)
def stock_take_export_csv(request, pk):
    """Export a stock take to CSV."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.view_stocktake', raise_exception=True)
def stock_take_export_pdf(request, pk):
    """Export a stock take to PDF."""
    # Implementation will be added
    pass


@login_required
@permission_required('inventory.add_stocktake', raise_exception=True)
def stock_take_create_cycle(request, pk):
    """Create a cycle count stock take."""
    # Implementation will be added
    pass
