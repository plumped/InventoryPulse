from accessmanagement.models import WarehouseAccess
from inventory.models import Warehouse

def get_accessible_warehouses(user):
    if user.is_superuser:
        return Warehouse.objects.filter(is_active=True)
    return Warehouse.objects.filter(
        is_active=True,
        id__in=WarehouseAccess.objects.filter(user=user).values_list('warehouse_id', flat=True)
    )
