"""
Service for product stock operations.

This module contains the ProductStockService class that handles business logic
related to product stock.
"""

import logging

from django.db import transaction
from django.utils import timezone

from ..repositories.product_warehouse_repository import ProductWarehouseRepository
from ..repositories.stock_movement_repository import StockMovementRepository

logger = logging.getLogger('inventory')


class ProductStockService:
    """Service for product stock operations."""
    
    def __init__(self):
        """Initialize the service with repositories."""
        self.product_warehouse_repository = ProductWarehouseRepository()
        self.stock_movement_repository = StockMovementRepository()
    
    def get_product_warehouse(self, product_id, warehouse_id):
        """
        Get a product warehouse by product and warehouse IDs.
        
        Args:
            product_id: The ID of the product
            warehouse_id: The ID of the warehouse
            
        Returns:
            The product warehouse for the given product and warehouse
            
        Raises:
            ProductWarehouse.DoesNotExist: If the product warehouse does not exist
        """
        return self.product_warehouse_repository.get_product_warehouse(product_id, warehouse_id)
    
    def get_product_warehouses(self, product_id):
        """
        Get all warehouses for a product.
        
        Args:
            product_id: The ID of the product
            
        Returns:
            QuerySet of product warehouses for the product
        """
        return self.product_warehouse_repository.get_product_warehouses_by_product(product_id)
    
    def get_warehouse_products(self, warehouse_id):
        """
        Get all products in a warehouse.
        
        Args:
            warehouse_id: The ID of the warehouse
            
        Returns:
            QuerySet of product warehouses for the warehouse
        """
        return self.product_warehouse_repository.get_product_warehouses_by_warehouse(warehouse_id)
    
    def get_products_with_stock(self, warehouse_id):
        """
        Get all products with stock in a warehouse.
        
        Args:
            warehouse_id: The ID of the warehouse
            
        Returns:
            QuerySet of product warehouses with stock > 0
        """
        return self.product_warehouse_repository.get_products_with_stock(warehouse_id)
    
    def get_products_with_low_stock(self, warehouse_id=None):
        """
        Get all products with low stock.
        
        Args:
            warehouse_id: The ID of the warehouse (optional)
            
        Returns:
            QuerySet of product warehouses with stock below minimum level
        """
        return self.product_warehouse_repository.get_products_with_low_stock(warehouse_id)
    
    def get_total_stock(self, product_id):
        """
        Get the total stock for a product across all warehouses.
        
        Args:
            product_id: The ID of the product
            
        Returns:
            The total stock for the product
        """
        return self.product_warehouse_repository.get_total_stock_for_product(product_id)
    
    @transaction.atomic
    def add_product_to_warehouse(self, product_id, warehouse_id, quantity=0, created_by=None):
        """
        Add a product to a warehouse.
        
        Args:
            product_id: The ID of the product
            warehouse_id: The ID of the warehouse
            quantity: The initial quantity (default: 0)
            created_by: The user who added the product (optional)
            
        Returns:
            The created product warehouse
            
        Raises:
            ValueError: If the product already exists in the warehouse
        """
        try:
            # Check if the product already exists in the warehouse
            try:
                existing = self.product_warehouse_repository.get_product_warehouse(product_id, warehouse_id)
                if existing:
                    raise ValueError(f"Product {product_id} already exists in warehouse {warehouse_id}")
            except:
                pass
            
            # Create product warehouse
            product_warehouse = self.product_warehouse_repository.create_product_warehouse(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=quantity
            )
            
            # Create stock movement if initial quantity > 0
            if quantity > 0:
                self.stock_movement_repository.create_movement(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    quantity=quantity,
                    movement_type='in',
                    reference='Initial stock',
                    created_by=created_by,
                    created_at=timezone.now()
                )
            
            logger.info(f"Product {product_id} added to warehouse {warehouse_id} with quantity {quantity}")
            
            return product_warehouse
            
        except Exception as e:
            logger.error(f"Error adding product to warehouse: {str(e)}")
            raise
    
    @transaction.atomic
    def adjust_stock(self, product_id, warehouse_id, quantity_change, reason, notes=None, created_by=None):
        """
        Adjust the stock of a product in a warehouse.
        
        Args:
            product_id: The ID of the product
            warehouse_id: The ID of the warehouse
            quantity_change: The change in quantity (positive or negative)
            reason: The reason for the adjustment
            notes: Additional notes (optional)
            created_by: The user who made the adjustment (optional)
            
        Returns:
            The updated product warehouse
            
        Raises:
            ValueError: If the quantity change is invalid or there is insufficient stock
        """
        try:
            if quantity_change == 0:
                raise ValueError("Quantity change must be non-zero")
            
            # Get or create product warehouse
            product_warehouse, created = self.product_warehouse_repository.get_or_create_product_warehouse(
                product_id=product_id,
                warehouse_id=warehouse_id
            )
            
            # Check if there is enough stock for negative adjustments
            if quantity_change < 0 and product_warehouse.quantity < abs(quantity_change):
                raise ValueError(f"Insufficient stock. Available: {product_warehouse.quantity}, Requested: {abs(quantity_change)}")
            
            # Update product warehouse quantity
            product_warehouse.quantity += quantity_change
            product_warehouse.save()
            
            # Create stock movement
            movement_type = 'in' if quantity_change > 0 else 'out'
            self.stock_movement_repository.create_movement(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=abs(quantity_change),
                movement_type=movement_type,
                reference=reason,
                notes=notes,
                created_by=created_by,
                created_at=timezone.now()
            )
            
            logger.info(
                f"Stock adjusted: {movement_type} {abs(quantity_change)} of product {product_id} "
                f"in warehouse {warehouse_id} for reason '{reason}'"
            )
            
            return product_warehouse
            
        except Exception as e:
            logger.error(f"Error adjusting stock: {str(e)}")
            raise
    
    @transaction.atomic
    def transfer_stock(self, product_id, from_warehouse_id, to_warehouse_id, quantity, 
                       notes=None, created_by=None):
        """
        Transfer stock from one warehouse to another.
        
        Args:
            product_id: The ID of the product
            from_warehouse_id: The ID of the source warehouse
            to_warehouse_id: The ID of the destination warehouse
            quantity: The quantity to transfer
            notes: Additional notes (optional)
            created_by: The user who made the transfer (optional)
            
        Returns:
            Tuple of (source_product_warehouse, destination_product_warehouse)
            
        Raises:
            ValueError: If the quantity is invalid or there is insufficient stock
        """
        try:
            if quantity <= 0:
                raise ValueError("Quantity must be greater than zero")
            
            if from_warehouse_id == to_warehouse_id:
                raise ValueError("Source and destination warehouses must be different")
            
            # Get source product warehouse
            source_product_warehouse = self.product_warehouse_repository.get_product_warehouse(
                product_id=product_id,
                warehouse_id=from_warehouse_id
            )
            
            # Check if there is enough stock
            if source_product_warehouse.quantity < quantity:
                raise ValueError(f"Insufficient stock. Available: {source_product_warehouse.quantity}, Requested: {quantity}")
            
            # Get or create destination product warehouse
            destination_product_warehouse, created = self.product_warehouse_repository.get_or_create_product_warehouse(
                product_id=product_id,
                warehouse_id=to_warehouse_id
            )
            
            # Update quantities
            source_product_warehouse.quantity -= quantity
            source_product_warehouse.save()
            
            destination_product_warehouse.quantity += quantity
            destination_product_warehouse.save()
            
            # Create stock movements
            self.stock_movement_repository.create_movement(
                product_id=product_id,
                warehouse_id=from_warehouse_id,
                quantity=quantity,
                movement_type='out',
                reference=f"Transfer to warehouse {to_warehouse_id}",
                notes=notes,
                created_by=created_by,
                created_at=timezone.now()
            )
            
            self.stock_movement_repository.create_movement(
                product_id=product_id,
                warehouse_id=to_warehouse_id,
                quantity=quantity,
                movement_type='in',
                reference=f"Transfer from warehouse {from_warehouse_id}",
                notes=notes,
                created_by=created_by,
                created_at=timezone.now()
            )
            
            logger.info(
                f"Stock transferred: {quantity} of product {product_id} "
                f"from warehouse {from_warehouse_id} to warehouse {to_warehouse_id}"
            )
            
            return source_product_warehouse, destination_product_warehouse
            
        except Exception as e:
            logger.error(f"Error transferring stock: {str(e)}")
            raise
    
    @transaction.atomic
    def bulk_add_products_to_warehouse(self, warehouse_id, product_quantities, created_by=None):
        """
        Add multiple products to a warehouse.
        
        Args:
            warehouse_id: The ID of the warehouse
            product_quantities: Dictionary mapping product IDs to quantities
            created_by: The user who added the products (optional)
            
        Returns:
            List of created product warehouses
            
        Raises:
            ValueError: If any product already exists in the warehouse
        """
        try:
            created_product_warehouses = []
            
            for product_id, quantity in product_quantities.items():
                product_warehouse = self.add_product_to_warehouse(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    quantity=quantity,
                    created_by=created_by
                )
                created_product_warehouses.append(product_warehouse)
            
            logger.info(f"Bulk added {len(product_quantities)} products to warehouse {warehouse_id}")
            
            return created_product_warehouses
            
        except Exception as e:
            logger.error(f"Error bulk adding products to warehouse: {str(e)}")
            raise
    
    @transaction.atomic
    def bulk_transfer_stock(self, from_warehouse_id, to_warehouse_id, product_quantities, 
                           notes=None, created_by=None):
        """
        Transfer multiple products from one warehouse to another.
        
        Args:
            from_warehouse_id: The ID of the source warehouse
            to_warehouse_id: The ID of the destination warehouse
            product_quantities: Dictionary mapping product IDs to quantities
            notes: Additional notes (optional)
            created_by: The user who made the transfer (optional)
            
        Returns:
            Dictionary mapping product IDs to tuples of (source_product_warehouse, destination_product_warehouse)
            
        Raises:
            ValueError: If any quantity is invalid or there is insufficient stock
        """
        try:
            if from_warehouse_id == to_warehouse_id:
                raise ValueError("Source and destination warehouses must be different")
            
            results = {}
            
            for product_id, quantity in product_quantities.items():
                source_product_warehouse, destination_product_warehouse = self.transfer_stock(
                    product_id=product_id,
                    from_warehouse_id=from_warehouse_id,
                    to_warehouse_id=to_warehouse_id,
                    quantity=quantity,
                    notes=notes,
                    created_by=created_by
                )
                results[product_id] = (source_product_warehouse, destination_product_warehouse)
            
            logger.info(
                f"Bulk transferred {len(product_quantities)} products "
                f"from warehouse {from_warehouse_id} to warehouse {to_warehouse_id}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error bulk transferring stock: {str(e)}")
            raise