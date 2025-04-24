"""
Views related to stock movements in the inventory app.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404

from accessmanagement.models import WarehouseAccess
from core.utils.pagination import paginate_queryset
from product_management.models.products_models import Product
from ..models import Warehouse
from ..services.stock_movement_service import StockMovementService
from ..services.warehouse_service import WarehouseService


@login_required
@permission_required('inventory.view_stockmovement', raise_exception=True)
def stock_movement_list(request):
    """List all stock movements with filtering and search."""
    # Initialize services
    stock_movement_service = StockMovementService()
    warehouse_service = WarehouseService()

    # Nur Bewegungen in Lagern, auf die der Benutzer Zugriff hat
    if request.user.is_superuser:
        accessible_warehouses = warehouse_service.get_active_warehouses()
    else:
        accessible_warehouses = [w for w in warehouse_service.get_active_warehouses()
                                 if WarehouseAccess.has_access(request.user, w, 'view')]

    # Get filter parameters
    warehouse_id = request.GET.get('warehouse', '')
    product_id = request.GET.get('product', '')
    movement_type = request.GET.get('type', '')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    # Check warehouse access if warehouse_id is provided
    if warehouse_id:
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
        if not request.user.is_superuser and not WarehouseAccess.has_access(request.user, warehouse, 'view'):
            messages.error(request, "Sie haben keinen Zugriff auf dieses Lager.")
            warehouse_id = None

    # Get movements with filters
    movements_list = stock_movement_service.get_stock_movements(
        warehouse_id=warehouse_id,
        product_id=product_id,
        movement_type=movement_type,
        date_from=date_from,
        date_to=date_to,
        search_query=search_query
    )

    # Filter by accessible warehouses
    if not request.user.is_superuser:
        movements_list = movements_list.filter(warehouse__in=accessible_warehouses)

    # Paginierung
    movements = paginate_queryset(movements_list, request.GET.get('page'), per_page=25)

    # Alle Produkte für den Filter
    products = Product.objects.all().order_by('name')

    context = {
        'movements': movements,
        'products': products,
        'warehouses': accessible_warehouses,
        'warehouse_id': warehouse_id,
        'product_id': product_id,
        'movement_type': movement_type,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
    }

    return render(request, 'inventory/stock_movement_list.html', context)
