"""
This module provides workflow utility functions for the order process.
It integrates with the admin_dashboard's workflow settings.
"""
from decimal import Decimal

from django.conf import settings


def get_workflow_settings():
    """
    Get the current workflow settings or return defaults if not available.
    """
    try:
        from admin_dashboard.models import WorkflowSettings
        workflow_settings = WorkflowSettings.objects.first()
        if workflow_settings:
            return workflow_settings
    except (ImportError, Exception):
        pass

    # Return a default workflow settings object with default values
    class DefaultWorkflowSettings:
        order_approval_required = True
        order_approval_threshold = Decimal('1000.00')
        skip_draft_for_small_orders = False
        small_order_threshold = Decimal('200.00')
        auto_approve_preferred_suppliers = False
        send_order_emails = False
        require_separate_approver = True

    return DefaultWorkflowSettings()


def get_initial_order_status(order):
    """
    Determine the initial status for a new order based on workflow settings.

    Args:
        order: The PurchaseOrder instance

    Returns:
        str: The initial status code
    """
    workflow_settings = get_workflow_settings()

    # Check if approval is required
    if not workflow_settings.order_approval_required:
        return 'approved'  # Skip approval process entirely

    # Check for small orders direct-to-pending
    if workflow_settings.skip_draft_for_small_orders:
        # Calculate order total
        order_total = sum(item.quantity_ordered * item.unit_price for item in order.items.all())
        if order_total <= workflow_settings.small_order_threshold:
            return 'pending'  # Skip draft for small orders

    # Default initial status
    return 'draft'


def check_auto_approval(order):
    workflow_settings = get_workflow_settings()
    # If approval is not required, always auto-approve
    if not workflow_settings.order_approval_required:
        return True

    # Check order total against threshold
    order_total = order.total
    if order_total <= workflow_settings.order_approval_threshold:
        return True

    # Check if preferred supplier auto-approval is enabled
    if workflow_settings.auto_approve_preferred_suppliers:
        # Check if the supplier is preferred
        try:
            from suppliers.models import Supplier
            supplier = Supplier.objects.get(id=order.supplier.id)
            # Assuming a supplier might have an is_preferred flag
            # This may need to be adjusted based on your actual data model
            if hasattr(supplier, 'is_preferred') and supplier.is_preferred:
                return True
        except Exception as e:
            print(f"Supplier check error: {e}")
    return False


def can_approve_order(user, order):
    """
    Check if a user can approve an order.

    Args:
        user: The User instance
        order: The PurchaseOrder instance

    Returns:
        bool: True if the user can approve the order
    """
    workflow_settings = get_workflow_settings()

    # First, check if the user has permission to approve orders
    if not user.has_perm('order.approve'):
        return False

    # If separate approver is required, check that the user is not the creator
    if workflow_settings.require_separate_approver and order.created_by == user:
        return False

    return True