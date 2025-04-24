"""
Service for stock movement operations.

This module contains the StockMovementService class that handles business logic
related to stock movements.
"""

import logging

from django.db import transaction
from django.utils import timezone

from ..repositories.product_warehouse_repository import ProductWarehouseRepository
from ..repositories.stock_movement_repository import StockMovementRepository

logger = logging.getLogger('inventory')


class StockMovementService:
    """Service for stock movement operations."""
    
    def __init__(self):
        """Initialize the service with repositories."""
        self.stock_movement_repository = StockMovementRepository()
        self.product_warehouse_repository = ProductWarehouseRepository()
    
    def get_stock_movement(self, movement_id):
        """
        Get a stock movement by ID.
        
        Args:
            movement_id: The ID of the stock movement
            
        Returns:
            The stock movement with the given ID
            
        Raises:
            StockMovement.DoesNotExist: If the stock movement does not exist
        """
        return self.stock_movement_repository.get_movement_by_id(movement_id)
    
    def get_stock_movements(self, **filters):
        """
        Get stock movements with filters.
        
        Args:
            **filters: Filters for stock movements
            
        Returns:
            QuerySet of stock movements matching the filters
        """
        return self.stock_movement_repository.filter_movements(
            warehouse_id=filters.get('warehouse_id'),
            product_id=filters.get('product_id'),
            movement_type=filters.get('movement_type'),
            date_from=filters.get('date_from'),
            date_to=filters.get('date_to'),
            search_query=filters.get('search_query')
        )
    
    @transaction.atomic
    def create_stock_movement(self, product_id, warehouse_id, quantity, movement_type, 
                              reference=None, notes=None, created_by=None, batch_number=None,
                              serial_numbers=None, expiry_date=None):
        """
        Create a stock movement and update product warehouse quantity.
        
        Args:
            product_id: The ID of the product
            warehouse_id: The ID of the warehouse
            quantity: The quantity to move
            movement_type: The type of movement ('in', 'out', 'transfer', etc.)
            reference: Reference for the movement (optional)
            notes: Notes for the movement (optional)
            created_by: The user who created the movement (optional)
            batch_number: The batch number for the movement (optional)
            serial_numbers: List of serial numbers for the movement (optional)
            expiry_date: Expiry date for the products (optional)
            
        Returns:
            The created stock movement
            
        Raises:
            ValueError: If the quantity is invalid or there is insufficient stock
        """
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")
        
        # Update product warehouse quantity
        try:
            product_warehouse, created = self.product_warehouse_repository.get_or_create_product_warehouse(
                product_id=product_id,
                warehouse_id=warehouse_id
            )
            
            # Check if there is enough stock for outgoing movements
            if movement_type == 'out' and product_warehouse.quantity < quantity:
                raise ValueError(f"Insufficient stock. Available: {product_warehouse.quantity}, Requested: {quantity}")
            
            # Update quantity based on movement type
            if movement_type == 'in':
                product_warehouse.quantity += quantity
            elif movement_type == 'out':
                product_warehouse.quantity -= quantity
            
            product_warehouse.save()
            
            # Create stock movement record
            movement = self.stock_movement_repository.create_movement(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=quantity,
                movement_type=movement_type,
                reference=reference,
                notes=notes,
                created_by=created_by,
                created_at=timezone.now(),
                batch_number=batch_number,
                expiry_date=expiry_date
            )
            
            # Handle serial numbers if provided
            if serial_numbers and hasattr(movement, 'serial_numbers'):
                movement.serial_numbers.add(*serial_numbers)
            
            logger.info(
                f"Stock movement created: {movement_type} {quantity} of product {product_id} "
                f"in warehouse {warehouse_id}"
            )
            
            return movement
            
        except Exception as e:
            logger.error(f"Error creating stock movement: {str(e)}")
            raise
    
    @transaction.atomic
    def transfer_stock(self, product_id, from_warehouse_id, to_warehouse_id, quantity, 
                       reference=None, notes=None, created_by=None, batch_number=None,
                       serial_numbers=None):
        """
        Transfer stock from one warehouse to another.
        
        Args:
            product_id: The ID of the product
            from_warehouse_id: The ID of the source warehouse
            to_warehouse_id: The ID of the destination warehouse
            quantity: The quantity to transfer
            reference: Reference for the transfer (optional)
            notes: Notes for the transfer (optional)
            created_by: The user who created the transfer (optional)
            batch_number: The batch number for the transfer (optional)
            serial_numbers: List of serial numbers for the transfer (optional)
            
        Returns:
            Tuple of (outgoing_movement, incoming_movement)
            
        Raises:
            ValueError: If the quantity is invalid or there is insufficient stock
        """
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")
        
        if from_warehouse_id == to_warehouse_id:
            raise ValueError("Source and destination warehouses must be different")
        
        try:
            # Create outgoing movement
            outgoing_movement = self.create_stock_movement(
                product_id=product_id,
                warehouse_id=from_warehouse_id,
                quantity=quantity,
                movement_type='out',
                reference=reference or f"Transfer to warehouse {to_warehouse_id}",
                notes=notes,
                created_by=created_by,
                batch_number=batch_number,
                serial_numbers=serial_numbers
            )
            
            # Create incoming movement
            incoming_movement = self.create_stock_movement(
                product_id=product_id,
                warehouse_id=to_warehouse_id,
                quantity=quantity,
                movement_type='in',
                reference=reference or f"Transfer from warehouse {from_warehouse_id}",
                notes=notes,
                created_by=created_by,
                batch_number=batch_number,
                serial_numbers=serial_numbers
            )
            
            logger.info(
                f"Stock transfer completed: {quantity} of product {product_id} "
                f"from warehouse {from_warehouse_id} to warehouse {to_warehouse_id}"
            )
            
            return outgoing_movement, incoming_movement
            
        except Exception as e:
            logger.error(f"Error transferring stock: {str(e)}")
            raise