"""
Views related to warehouse management in the inventory app.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect

from accessmanagement.models import WarehouseAccess
from core.models import Warehouse
from core.utils.pagination import paginate_queryset
from master_data.models.organisations_models import Department
from ..forms import WarehouseForm
from ..services.product_stock_service import ProductStockService
from ..services.warehouse_service import WarehouseService


@login_required
@permission_required('inventory.view_warehouse', raise_exception=True)
def warehouse_list(request):
    """List all warehouses."""
    # Initialize services
    warehouse_service = WarehouseService()

    # Get search parameter
    search_query = request.GET.get('search', '')

    # Get warehouses with search filter
    if search_query:
        warehouses_list = warehouse_service.search_warehouses(search_query)
    else:
        warehouses_list = warehouse_service.get_active_warehouses()

    # Paginierung
    warehouses = paginate_queryset(warehouses_list, request.GET.get('page'), per_page=10)

    context = {
        'warehouses': warehouses,
        'search_query': search_query,
    }

    return render(request, 'inventory/warehouse_list.html', context)


@login_required
@permission_required('inventory.add_warehouse', raise_exception=True)
def warehouse_create(request):
    """Create a new warehouse."""
    # Initialize services
    warehouse_service = WarehouseService()

    if request.method == 'POST':
        form = WarehouseForm(request.POST)
        if form.is_valid():
            try:
                # Create warehouse using service
                warehouse = warehouse_service.create_warehouse(
                    name=form.cleaned_data['name'],
                    code=form.cleaned_data['code'],
                    address=form.cleaned_data.get('address'),
                    description=form.cleaned_data.get('description'),
                    is_active=form.cleaned_data.get('is_active', True),
                    created_by=request.user
                )

                messages.success(request, f'Lager "{warehouse.name}" wurde erfolgreich erstellt.')
                return redirect('warehouse_detail', pk=warehouse.pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = WarehouseForm()

    context = {
        'form': form,
        'title': 'Neues Lager erstellen',
    }

    return render(request, 'inventory/warehouse_form.html', context)


@login_required
@permission_required('inventory.view_warehouse', raise_exception=True)
def warehouse_detail(request, pk):
    """View details of a warehouse."""
    # Initialize services
    warehouse_service = WarehouseService()
    product_stock_service = ProductStockService()

    try:
        # Get warehouse using service
        warehouse = warehouse_service.get_warehouse(pk)

        # Get products in warehouse
        products = product_stock_service.get_warehouse_products(warehouse.id)

        # Paginierung
        paginated_products = paginate_queryset(products, request.GET.get('page'), per_page=25)

        context = {
            'warehouse': warehouse,
            'products': paginated_products,
        }

        return render(request, 'inventory/warehouse_detail.html', context)
    except Warehouse.DoesNotExist:
        messages.error(request, 'Das angeforderte Lager existiert nicht.')
        return redirect('warehouse_list')


@login_required
@permission_required('inventory.change_warehouse', raise_exception=True)
def warehouse_update(request, pk):
    """Update a warehouse."""
    # Initialize services
    warehouse_service = WarehouseService()

    try:
        # Get warehouse using service
        warehouse = warehouse_service.get_warehouse(pk)

        if request.method == 'POST':
            form = WarehouseForm(request.POST, instance=warehouse)
            if form.is_valid():
                try:
                    # Update warehouse using service
                    updated_warehouse = warehouse_service.update_warehouse(
                        warehouse_id=warehouse.id,
                        name=form.cleaned_data['name'],
                        code=form.cleaned_data['code'],
                        address=form.cleaned_data.get('address'),
                        description=form.cleaned_data.get('description'),
                        is_active=form.cleaned_data.get('is_active', True)
                    )

                    messages.success(request, f'Lager "{updated_warehouse.name}" wurde erfolgreich aktualisiert.')
                    return redirect('warehouse_detail', pk=updated_warehouse.pk)
                except ValueError as e:
                    messages.error(request, str(e))
        else:
            form = WarehouseForm(instance=warehouse)

        context = {
            'form': form,
            'warehouse': warehouse,
            'title': f'Lager "{warehouse.name}" bearbeiten',
        }

        return render(request, 'inventory/warehouse_form.html', context)
    except Warehouse.DoesNotExist:
        messages.error(request, 'Das angeforderte Lager existiert nicht.')
        return redirect('warehouse_list')


@login_required
@permission_required('inventory.delete_warehouse', raise_exception=True)
def warehouse_delete(request, pk):
    """Delete a warehouse."""
    # Initialize services
    warehouse_service = WarehouseService()

    try:
        # Get warehouse using service
        warehouse = warehouse_service.get_warehouse(pk)

        if request.method == 'POST':
            try:
                # Delete warehouse using service
                warehouse_service.delete_warehouse(warehouse.id)

                messages.success(request, f'Lager "{warehouse.name}" wurde erfolgreich gelöscht.')
                return redirect('warehouse_list')
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('warehouse_detail', pk=warehouse.pk)

        context = {
            'warehouse': warehouse,
            'title': f'Lager "{warehouse.name}" löschen',
            'message': 'Sind Sie sicher, dass Sie dieses Lager löschen möchten?',
        }

        return render(request, 'inventory/confirm_delete.html', context)
    except Warehouse.DoesNotExist:
        messages.error(request, 'Das angeforderte Lager existiert nicht.')
        return redirect('warehouse_list')


@login_required
@permission_required('accessmanagement.view_warehouseaccess', raise_exception=True)
def warehouse_access_management(request):
    """Manage warehouse access."""
    # Implementation will be added
    pass


@login_required
@permission_required('accessmanagement.delete_warehouseaccess', raise_exception=True)
def warehouse_access_delete(request, pk):
    """Delete warehouse access."""
    # Implementation will be added
    pass


@login_required
@permission_required('accessmanagement.add_warehouseaccess', raise_exception=True)
def warehouse_access_add(request):
    """Add warehouse access."""
    # Implementation will be added
    pass


@login_required
@permission_required('accessmanagement.change_warehouseaccess', raise_exception=True)
def warehouse_access_update(request, pk):
    """Update warehouse access."""
    # Implementation will be added
    pass


class WarehouseAccessForm(forms.ModelForm):
    """Form for warehouse access."""
    class Meta:
        model = WarehouseAccess
        fields = ['warehouse', 'department', 'can_view', 'can_edit', 'can_manage_stock']
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'can_view': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_manage_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['warehouse'].queryset = Warehouse.objects.filter(is_active=True).order_by('name')
        self.fields['department'].queryset = Department.objects.all().order_by('name')
