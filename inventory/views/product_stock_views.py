"""
Views related to product stock management in the inventory app.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404

from accessmanagement.models import WarehouseAccess
from core.utils.pagination import paginate_queryset
from product_management.models.products_models import Product
from ..forms import StockAdjustmentForm
from ..models import Warehouse
from ..services.product_stock_service import ProductStockService
from ..services.warehouse_service import WarehouseService


@login_required
@permission_required('inventory.view_productwarehouse', raise_exception=True)
def product_warehouses(request, product_id):
    """View warehouses for a product."""
    # Initialize services
    product_stock_service = ProductStockService()

    try:
        # Get product
        product = get_object_or_404(Product, pk=product_id)

        # Get warehouses for product
        product_warehouses = product_stock_service.get_product_warehouses(product_id)

        # Filter by accessible warehouses if not superuser
        if not request.user.is_superuser:
            accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                                    if WarehouseAccess.has_access(request.user, w, 'view')]
            product_warehouses = product_warehouses.filter(warehouse__in=accessible_warehouses)

        # Paginierung
        paginated_warehouses = paginate_queryset(product_warehouses, request.GET.get('page'), per_page=10)

        context = {
            'product': product,
            'product_warehouses': paginated_warehouses,
        }

        return render(request, 'inventory/product_warehouses.html', context)
    except Product.DoesNotExist:
        messages.error(request, 'Das angeforderte Produkt existiert nicht.')
        return redirect('product_list')


@login_required
@permission_required('inventory.add_productwarehouse', raise_exception=True)
def product_add_to_warehouse(request, warehouse_id):
    """Add a product to a warehouse."""
    # Initialize services
    product_stock_service = ProductStockService()
    warehouse_service = WarehouseService()

    try:
        # Get warehouse
        warehouse = warehouse_service.get_warehouse(warehouse_id)

        # Check access
        if not request.user.is_superuser and not WarehouseAccess.has_access(request.user, warehouse, 'manage_stock'):
            messages.error(request, 'Sie haben keine Berechtigung, Produkte zu diesem Lager hinzuzufügen.')
            return redirect('warehouse_detail', pk=warehouse_id)

        if request.method == 'POST':
            product_id = request.POST.get('product_id')
            quantity = request.POST.get('quantity', 0)

            try:
                quantity = int(quantity)

                # Add product to warehouse
                product_stock_service.add_product_to_warehouse(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    quantity=quantity,
                    created_by=request.user
                )

                messages.success(request, f'Produkt wurde erfolgreich zum Lager hinzugefügt.')
                return redirect('warehouse_detail', pk=warehouse_id)
            except ValueError as e:
                messages.error(request, str(e))

        # Get products not in warehouse
        existing_product_ids = product_stock_service.get_warehouse_products(warehouse_id).values_list('product_id', flat=True)
        available_products = Product.objects.exclude(id__in=existing_product_ids).order_by('name')

        context = {
            'warehouse': warehouse,
            'products': available_products,
        }

        return render(request, 'inventory/product_add_to_warehouse.html', context)
    except Warehouse.DoesNotExist:
        messages.error(request, 'Das angeforderte Lager existiert nicht.')
        return redirect('warehouse_list')


@login_required
@permission_required('inventory.add_productwarehouse', raise_exception=True)
def bulk_add_products_to_warehouse(request, warehouse_id):
    """Add multiple products to a warehouse."""
    # Initialize services
    product_stock_service = ProductStockService()
    warehouse_service = WarehouseService()

    try:
        # Get warehouse
        warehouse = warehouse_service.get_warehouse(warehouse_id)

        # Check access
        if not request.user.is_superuser and not WarehouseAccess.has_access(request.user, warehouse, 'manage_stock'):
            messages.error(request, 'Sie haben keine Berechtigung, Produkte zu diesem Lager hinzuzufügen.')
            return redirect('warehouse_detail', pk=warehouse_id)

        if request.method == 'POST':
            product_quantities = {}

            for key, value in request.POST.items():
                if key.startswith('product_') and value:
                    try:
                        product_id = int(key.replace('product_', ''))
                        quantity = int(value)
                        product_quantities[product_id] = quantity
                    except ValueError:
                        pass

            if product_quantities:
                try:
                    # Add products to warehouse
                    product_stock_service.bulk_add_products_to_warehouse(
                        warehouse_id=warehouse_id,
                        product_quantities=product_quantities,
                        created_by=request.user
                    )

                    messages.success(request, f'{len(product_quantities)} Produkte wurden erfolgreich zum Lager hinzugefügt.')
                    return redirect('warehouse_detail', pk=warehouse_id)
                except ValueError as e:
                    messages.error(request, str(e))

        # Get products not in warehouse
        existing_product_ids = product_stock_service.get_warehouse_products(warehouse_id).values_list('product_id', flat=True)
        available_products = Product.objects.exclude(id__in=existing_product_ids).order_by('name')

        context = {
            'warehouse': warehouse,
            'products': available_products,
        }

        return render(request, 'inventory/bulk_add_products.html', context)
    except Warehouse.DoesNotExist:
        messages.error(request, 'Das angeforderte Lager existiert nicht.')
        return redirect('warehouse_list')


@login_required
@permission_required('inventory.change_productwarehouse', raise_exception=True)
def bulk_warehouse_transfer(request):
    """Transfer products between warehouses."""
    # Initialize services
    product_stock_service = ProductStockService()
    warehouse_service = WarehouseService()

    # Get warehouses
    warehouses = warehouse_service.get_active_warehouses()

    # Filter by accessible warehouses if not superuser
    if not request.user.is_superuser:
        warehouses = [w for w in warehouses if WarehouseAccess.has_access(request.user, w, 'manage_stock')]

    if request.method == 'POST':
        from_warehouse_id = request.POST.get('from_warehouse')
        to_warehouse_id = request.POST.get('to_warehouse')

        if from_warehouse_id == to_warehouse_id:
            messages.error(request, 'Quell- und Ziellager müssen unterschiedlich sein.')
        else:
            product_quantities = {}

            for key, value in request.POST.items():
                if key.startswith('product_') and value:
                    try:
                        product_id = int(key.replace('product_', ''))
                        quantity = int(value)
                        if quantity > 0:
                            product_quantities[product_id] = quantity
                    except ValueError:
                        pass

            if product_quantities:
                try:
                    # Transfer products
                    product_stock_service.bulk_transfer_stock(
                        from_warehouse_id=from_warehouse_id,
                        to_warehouse_id=to_warehouse_id,
                        product_quantities=product_quantities,
                        notes=f"Bulk transfer initiated by {request.user.username}",
                        created_by=request.user
                    )

                    messages.success(request, f'{len(product_quantities)} Produkte wurden erfolgreich übertragen.')
                    return redirect('warehouse_detail', pk=to_warehouse_id)
                except ValueError as e:
                    messages.error(request, str(e))

    context = {
        'warehouses': warehouses,
    }

    return render(request, 'inventory/bulk_warehouse_transfer.html', context)


@login_required
@permission_required('inventory.change_productwarehouse', raise_exception=True)
def stock_adjustment(request, product_id, warehouse_id=None):
    """Adjust stock for a product."""
    # Initialize services
    product_stock_service = ProductStockService()
    warehouse_service = WarehouseService()

    try:
        # Get product
        product = get_object_or_404(Product, pk=product_id)

        # Get warehouses for product
        if warehouse_id:
            warehouse = warehouse_service.get_warehouse(warehouse_id)
            warehouses = [warehouse]

            # Check access
            if not request.user.is_superuser and not WarehouseAccess.has_access(request.user, warehouse, 'manage_stock'):
                messages.error(request, 'Sie haben keine Berechtigung, den Bestand in diesem Lager anzupassen.')
                return redirect('product_detail', pk=product_id)
        else:
            # Get all warehouses with this product
            product_warehouses = product_stock_service.get_product_warehouses(product_id)
            warehouse_ids = product_warehouses.values_list('warehouse_id', flat=True)
            warehouses = warehouse_service.get_active_warehouses().filter(id__in=warehouse_ids)

            # Filter by accessible warehouses if not superuser
            if not request.user.is_superuser:
                warehouses = [w for w in warehouses if WarehouseAccess.has_access(request.user, w, 'manage_stock')]

        if request.method == 'POST':
            form = StockAdjustmentForm(request.POST, warehouses=warehouses)
            if form.is_valid():
                try:
                    warehouse_id = form.cleaned_data['warehouse'].id
                    quantity_change = form.cleaned_data['quantity_change']
                    reason = form.cleaned_data['reason']
                    notes = form.cleaned_data.get('notes')

                    # Adjust stock
                    product_stock_service.adjust_stock(
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                        quantity_change=quantity_change,
                        reason=reason,
                        notes=notes,
                        created_by=request.user
                    )

                    messages.success(request, f'Bestand wurde erfolgreich angepasst.')
                    return redirect('product_detail', pk=product_id)
                except ValueError as e:
                    messages.error(request, str(e))
        else:
            form = StockAdjustmentForm(warehouses=warehouses)
            if warehouse_id:
                form.fields['warehouse'].initial = warehouse_id

        context = {
            'form': form,
            'product': product,
            'title': f'Bestand anpassen für {product.name}',
        }

        return render(request, 'inventory/stock_adjustment_form.html', context)
    except Product.DoesNotExist:
        messages.error(request, 'Das angeforderte Produkt existiert nicht.')
        return redirect('product_list')
    except Warehouse.DoesNotExist:
        messages.error(request, 'Das angeforderte Lager existiert nicht.')
        return redirect('product_detail', pk=product_id)
