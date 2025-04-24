"""
Repository for Warehouse model.

This module contains the WarehouseRepository class that handles all data access
operations related to the Warehouse model.
"""

from django.db.models import Q

from core.models import Warehouse
from .base import BaseRepository


class WarehouseRepository(BaseRepository):
    """Repository for Warehouse model."""

    model_class = Warehouse

    def get_warehouse_by_id(self, warehouse_id):
        """
        Get a warehouse by its ID.

        Args:
            warehouse_id: The ID of the warehouse

        Returns:
            The warehouse with the given ID

        Raises:
            Warehouse.DoesNotExist: If the warehouse does not exist
        """
        return self.get_by_id(warehouse_id)

    def get_active_warehouses(self):
        """
        Get all active warehouses.

        Returns:
            QuerySet of active warehouses
        """
        return self.filter(is_active=True)

    def search_warehouses(self, search_query):
        """
        Search for warehouses by name or code.

        Args:
            search_query: The search query

        Returns:
            QuerySet of matching warehouses
        """
        if not search_query:
            return self.get_active_warehouses()

        query = Q(name__icontains=search_query) | Q(code__icontains=search_query)

        return self.filter_with_q(query & Q(is_active=True))

    def create_warehouse(self, **kwargs):
        """
        Create a new warehouse.

        Args:
            **kwargs: Warehouse attributes

        Returns:
            The created warehouse
        """
        return self.create(**kwargs)

    def update_warehouse(self, warehouse, **kwargs):
        """
        Update an existing warehouse.

        Args:
            warehouse: The warehouse to update
            **kwargs: Attributes to update

        Returns:
            The updated warehouse
        """
        return self.update(warehouse, **kwargs)

    def delete_warehouse(self, warehouse):
        """
        Delete a warehouse.

        Args:
            warehouse: The warehouse to delete
        """
        self.delete(warehouse)

    def soft_delete_warehouse(self, warehouse):
        """
        Soft delete a warehouse by marking it as inactive.

        Args:
            warehouse: The warehouse to soft delete

        Returns:
            The updated warehouse
        """
        return self.update(warehouse, is_active=False)
