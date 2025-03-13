# In inventory/utils.py oder einer ähnlichen Datei
from accessmanagement.models import WarehouseAccess


def user_has_warehouse_access(user, warehouse, permission_type='view'):
    """
    Überprüft, ob ein Benutzer Zugriff auf ein bestimmtes Lager hat.

    Args:
        user: Der Benutzer
        warehouse: Das Lager
        permission_type: Art des Zugriffs ('view', 'edit', 'manage_stock')

    Returns:
        bool: True, wenn Zugriff erlaubt, sonst False
    """
    # Admin hat immer Zugriff
    if user.is_superuser:
        return True

    # Korrekt auf die Abteilungen über das Benutzerprofil zugreifen
    try:
        user_departments = user.profile.departments.all()
    except:
        # Fallback zur direkten Beziehung, falls das Profil nicht existiert
        user_departments = user.departments.all()

    for department in user_departments:
        try:
            access = WarehouseAccess.objects.get(warehouse=warehouse, department=department)
            if permission_type == 'view' and access.can_view:
                return True
            elif permission_type == 'edit' and access.can_edit:
                return True
            elif permission_type == 'manage_stock' and access.can_manage_stock:
                return True
        except WarehouseAccess.DoesNotExist:
            continue

    return False