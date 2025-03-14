from rest_framework import permissions
from accessmanagement.permissions import has_permission


class HasModulePermission(permissions.BasePermission):
    """
    Custom permission to check if the user has access to the specific module and action.
    """

    def __init__(self, module, action):
        self.module = module
        self.action = action

    def has_permission(self, request, view):
        # Superuser always has permission
        if request.user.is_superuser:
            return True

        # Convert REST methods to permission actions
        if self.action == 'view':
            if request.method in ['GET', 'HEAD', 'OPTIONS']:
                return has_permission(request.user, self.module, 'view')

        elif self.action == 'edit':
            if request.method in ['PUT', 'PATCH']:
                return has_permission(request.user, self.module, 'edit')

        elif self.action == 'create':
            if request.method in ['POST']:
                return has_permission(request.user, self.module, 'create')

        elif self.action == 'delete':
            if request.method in ['DELETE']:
                return has_permission(request.user, self.module, 'delete')

        # If we reach here, no specific permission matches
        return False


class ProductPermission(permissions.BasePermission):
    """
    Permission for product-related views
    """

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        if request.method in permissions.SAFE_METHODS:
            return has_permission(request.user, 'product', 'view')
        elif request.method == 'POST':
            return has_permission(request.user, 'product', 'create')
        elif request.method in ['PUT', 'PATCH']:
            return has_permission(request.user, 'product', 'edit')
        elif request.method == 'DELETE':
            return has_permission(request.user, 'product', 'delete')
        return False


class InventoryPermission(permissions.BasePermission):
    """
    Permission for inventory-related views
    """

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        if request.method in permissions.SAFE_METHODS:
            return has_permission(request.user, 'inventory', 'view')
        elif request.method == 'POST':
            return has_permission(request.user, 'inventory', 'create')
        elif request.method in ['PUT', 'PATCH']:
            return has_permission(request.user, 'inventory', 'edit')
        elif request.method == 'DELETE':
            return has_permission(request.user, 'inventory', 'delete')
        return False


class SupplierPermission(permissions.BasePermission):
    """
    Permission for supplier-related views
    """

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        if request.method in permissions.SAFE_METHODS:
            return has_permission(request.user, 'supplier', 'view')
        elif request.method == 'POST':
            return has_permission(request.user, 'supplier', 'create')
        elif request.method in ['PUT', 'PATCH']:
            return has_permission(request.user, 'supplier', 'edit')
        elif request.method == 'DELETE':
            return has_permission(request.user, 'supplier', 'delete')
        return False


class OrderPermission(permissions.BasePermission):
    """
    Permission for order-related views
    """

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        if request.method in permissions.SAFE_METHODS:
            return has_permission(request.user, 'order', 'view')
        elif request.method == 'POST':
            return has_permission(request.user, 'order', 'create')
        elif request.method in ['PUT', 'PATCH']:
            return has_permission(request.user, 'order', 'edit')
        elif request.method == 'DELETE':
            return has_permission(request.user, 'order', 'delete')
        return False


class OrderApprovePermission(permissions.BasePermission):
    """
    Permission for approving orders
    """

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        return has_permission(request.user, 'order', 'approve')


class UserPermission(permissions.BasePermission):
    """
    Permission für den User-API-Endpunkt.
    Erlaubt nur Lesezugriff (keine Schreiboperation)
    """

    def has_permission(self, request, view):
        # Superuser haben immer Zugriff
        if request.user.is_superuser:
            return True

        # Nur sichere Methoden (GET, HEAD, OPTIONS) für alle anderen Benutzer erlauben
        if request.method in permissions.SAFE_METHODS:
            # Optional: Hier könnte man noch eine spezielle Berechtigung prüfen
            # return has_permission(request.user, 'user', 'view')
            return True

        # Keine Schreiboperationen erlauben
        return False