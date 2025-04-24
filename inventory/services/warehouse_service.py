"""
Service for warehouse operations.

This module contains the WarehouseService class that handles business logic
related to warehouses.
"""

import logging

from django.db import transaction
from django.utils import timezone

from core.models import Warehouse
from ..repositories.warehouse_repository import WarehouseRepository

logger = logging.getLogger('inventory')


class WarehouseService:
    """Service for warehouse operations."""

    def __init__(self):
        """Initialize the service with repositories."""
        self.warehouse_repository = WarehouseRepository()

    def get_warehouse(self, warehouse_id):
        """
        Get a warehouse by ID.

        Args:
            warehouse_id: The ID of the warehouse

        Returns:
            The warehouse with the given ID

        Raises:
            Warehouse.DoesNotExist: If the warehouse does not exist
        """
        return self.warehouse_repository.get_warehouse_by_id(warehouse_id)

    def get_active_warehouses(self):
        """
        Get all active warehouses.

        Returns:
            QuerySet of active warehouses
        """
        return self.warehouse_repository.get_active_warehouses()

    def search_warehouses(self, search_query):
        """
        Search for warehouses by name or code.

        Args:
            search_query: The search query

        Returns:
            QuerySet of matching warehouses
        """
        return self.warehouse_repository.search_warehouses(search_query)

    @transaction.atomic
    def create_warehouse(self, name, code, address=None, description=None, is_active=True, created_by=None):
        """
        Create a new warehouse.

        Args:
            name: The name of the warehouse
            code: The code of the warehouse
            address: The address of the warehouse (optional)
            description: The description of the warehouse (optional)
            is_active: Whether the warehouse is active (default: True)
            created_by: The user who created the warehouse (optional)

        Returns:
            The created warehouse

        Raises:
            ValueError: If a warehouse with the same code already exists
        """
        try:
            # Check if a warehouse with the same code already exists
            try:
                existing_warehouse = self.warehouse_repository.filter(code=code).first()
                if existing_warehouse:
                    raise ValueError(f"A warehouse with code '{code}' already exists")
            except Warehouse.DoesNotExist:
                pass

            # Create warehouse
            warehouse = self.warehouse_repository.create_warehouse(
                name=name,
                code=code,
                address=address,
                description=description,
                is_active=is_active,
                created_by=created_by,
                created_at=timezone.now()
            )

            logger.info(f"Warehouse created: {name} ({code})")

            return warehouse

        except Exception as e:
            logger.error(f"Error creating warehouse: {str(e)}")
            raise

    @transaction.atomic
    def update_warehouse(self, warehouse_id, **kwargs):
        """
        Update an existing warehouse.

        Args:
            warehouse_id: The ID of the warehouse
            **kwargs: Attributes to update

        Returns:
            The updated warehouse

        Raises:
            Warehouse.DoesNotExist: If the warehouse does not exist
            ValueError: If a warehouse with the same code already exists
        """
        try:
            warehouse = self.get_warehouse(warehouse_id)

            # Check if code is being updated and if a warehouse with the same code already exists
            if 'code' in kwargs and kwargs['code'] != warehouse.code:
                try:
                    existing_warehouse = self.warehouse_repository.filter(code=kwargs['code']).first()
                    if existing_warehouse and existing_warehouse.id != warehouse_id:
                        raise ValueError(f"A warehouse with code '{kwargs['code']}' already exists")
                except Warehouse.DoesNotExist:
                    pass

            # Update warehouse
            updated_warehouse = self.warehouse_repository.update_warehouse(
                warehouse=warehouse,
                **kwargs
            )

            logger.info(f"Warehouse updated: {warehouse.name} ({warehouse.code})")

            return updated_warehouse

        except Exception as e:
            logger.error(f"Error updating warehouse: {str(e)}")
            raise

    @transaction.atomic
    def delete_warehouse(self, warehouse_id):
        """
        Delete a warehouse.

        Args:
            warehouse_id: The ID of the warehouse

        Raises:
            Warehouse.DoesNotExist: If the warehouse does not exist
            ValueError: If the warehouse has associated products
        """
        try:
            warehouse = self.get_warehouse(warehouse_id)

            # Check if the warehouse has associated products
            if hasattr(warehouse, 'productwarehouse_set') and warehouse.productwarehouse_set.exists():
                raise ValueError("Cannot delete warehouse with associated products")

            # Delete warehouse
            self.warehouse_repository.delete_warehouse(warehouse)

            logger.info(f"Warehouse deleted: {warehouse.name} ({warehouse.code})")

        except Exception as e:
            logger.error(f"Error deleting warehouse: {str(e)}")
            raise

    @transaction.atomic
    def deactivate_warehouse(self, warehouse_id):
        """
        Deactivate a warehouse.

        Args:
            warehouse_id: The ID of the warehouse

        Returns:
            The updated warehouse

        Raises:
            Warehouse.DoesNotExist: If the warehouse does not exist
        """
        try:
            warehouse = self.get_warehouse(warehouse_id)

            # Deactivate warehouse
            updated_warehouse = self.warehouse_repository.update_warehouse(
                warehouse=warehouse,
                is_active=False
            )

            logger.info(f"Warehouse deactivated: {warehouse.name} ({warehouse.code})")

            return updated_warehouse

        except Exception as e:
            logger.error(f"Error deactivating warehouse: {str(e)}")
            raise

    @transaction.atomic
    def activate_warehouse(self, warehouse_id):
        """
        Activate a warehouse.

        Args:
            warehouse_id: The ID of the warehouse

        Returns:
            The updated warehouse

        Raises:
            Warehouse.DoesNotExist: If the warehouse does not exist
        """
        try:
            warehouse = self.get_warehouse(warehouse_id)

            # Activate warehouse
            updated_warehouse = self.warehouse_repository.update_warehouse(
                warehouse=warehouse,
                is_active=True
            )

            logger.info(f"Warehouse activated: {warehouse.name} ({warehouse.code})")

            return updated_warehouse

        except Exception as e:
            logger.error(f"Error activating warehouse: {str(e)}")
            raise
