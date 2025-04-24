"""
Service for stock take operations.

This module contains the StockTakeService class that handles business logic
related to stock takes.
"""

import logging

from django.db import transaction
from django.utils import timezone

from ..repositories.product_warehouse_repository import ProductWarehouseRepository
from ..repositories.stock_movement_repository import StockMovementRepository
from ..repositories.stock_take_repository import StockTakeRepository, StockTakeItemRepository

logger = logging.getLogger('inventory')


class StockTakeService:
    """Service for stock take operations."""
    
    def __init__(self):
        """Initialize the service with repositories."""
        self.stock_take_repository = StockTakeRepository()
        self.stock_take_item_repository = StockTakeItemRepository()
        self.product_warehouse_repository = ProductWarehouseRepository()
        self.stock_movement_repository = StockMovementRepository()
    
    def get_stock_take(self, stock_take_id):
        """
        Get a stock take by ID.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            The stock take with the given ID
            
        Raises:
            StockTake.DoesNotExist: If the stock take does not exist
        """
        return self.stock_take_repository.get_stock_take_by_id(stock_take_id)
    
    def get_stock_takes(self, **filters):
        """
        Get stock takes with filters.
        
        Args:
            **filters: Filters for stock takes
            
        Returns:
            QuerySet of stock takes matching the filters
        """
        return self.stock_take_repository.filter_stock_takes(
            warehouse_id=filters.get('warehouse_id'),
            status=filters.get('status'),
            inventory_type=filters.get('inventory_type'),
            date_from=filters.get('date_from'),
            date_to=filters.get('date_to'),
            search_query=filters.get('search_query')
        )
    
    def get_stock_take_item(self, item_id):
        """
        Get a stock take item by ID.
        
        Args:
            item_id: The ID of the stock take item
            
        Returns:
            The stock take item with the given ID
            
        Raises:
            StockTakeItem.DoesNotExist: If the stock take item does not exist
        """
        return self.stock_take_item_repository.get_item_by_id(item_id)
    
    def get_stock_take_items(self, stock_take_id):
        """
        Get all items for a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            QuerySet of items for the stock take
        """
        return self.stock_take_item_repository.get_items_by_stock_take(stock_take_id)
    
    def get_uncounted_items(self, stock_take_id):
        """
        Get all uncounted items for a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            QuerySet of uncounted items for the stock take
        """
        return self.stock_take_item_repository.get_uncounted_items(stock_take_id)
    
    def get_counted_items(self, stock_take_id):
        """
        Get all counted items for a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            QuerySet of counted items for the stock take
        """
        return self.stock_take_item_repository.get_counted_items(stock_take_id)
    
    def get_discrepancy_items(self, stock_take_id):
        """
        Get all items with discrepancies for a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            QuerySet of items with discrepancies for the stock take
        """
        return self.stock_take_item_repository.get_discrepancy_items(stock_take_id)
    
    @transaction.atomic
    def create_stock_take(self, warehouse_id, name, description=None, inventory_type='full',
                          cycle_count_category=None, count_frequency=None, created_by=None):
        """
        Create a new stock take.
        
        Args:
            warehouse_id: The ID of the warehouse
            name: The name of the stock take
            description: The description of the stock take (optional)
            inventory_type: The type of inventory ('full', 'partial', 'rolling')
            cycle_count_category: The category for cycle counting (optional)
            count_frequency: The frequency for cycle counting (optional)
            created_by: The user who created the stock take (optional)
            
        Returns:
            The created stock take
            
        Raises:
            ValueError: If the warehouse does not exist or the inventory type is invalid
        """
        try:
            # Create stock take
            stock_take = self.stock_take_repository.create_stock_take(
                warehouse_id=warehouse_id,
                name=name,
                description=description,
                inventory_type=inventory_type,
                cycle_count_category=cycle_count_category,
                count_frequency=count_frequency,
                created_by=created_by,
                status='planned',
                start_date=timezone.now().date()
            )
            
            # For rolling inventories, set the last cycle date
            if inventory_type == 'rolling' and count_frequency:
                stock_take.last_cycle_date = timezone.now().date()
                stock_take.save()
            
            logger.info(f"Stock take created: {name} for warehouse {warehouse_id}")
            
            return stock_take
            
        except Exception as e:
            logger.error(f"Error creating stock take: {str(e)}")
            raise
    
    @transaction.atomic
    def add_items_to_stock_take(self, stock_take_id, product_ids=None, category_id=None):
        """
        Add items to a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            product_ids: List of product IDs to add (optional)
            category_id: The ID of the product category to add (optional)
            
        Returns:
            List of created stock take items
            
        Raises:
            ValueError: If the stock take does not exist or is not in 'planned' status
        """
        try:
            stock_take = self.get_stock_take(stock_take_id)
            
            if stock_take.status != 'planned':
                raise ValueError("Items can only be added to stock takes in 'planned' status")
            
            created_items = []
            
            # If specific product IDs are provided
            if product_ids:
                for product_id in product_ids:
                    # Get current stock level
                    product_warehouse = self.product_warehouse_repository.get_product_warehouse(
                        product_id=product_id,
                        warehouse_id=stock_take.warehouse_id
                    )
                    
                    # Create stock take item
                    item = self.stock_take_item_repository.create_item(
                        stock_take=stock_take,
                        product_id=product_id,
                        expected_quantity=product_warehouse.quantity if product_warehouse else 0,
                        counted=False
                    )
                    
                    created_items.append(item)
            
            # If a category is provided
            elif category_id:
                # Get all products in the category
                product_warehouses = self.product_warehouse_repository.get_product_warehouses_by_warehouse(
                    warehouse_id=stock_take.warehouse_id
                ).filter(product__category_id=category_id)
                
                for product_warehouse in product_warehouses:
                    # Create stock take item
                    item = self.stock_take_item_repository.create_item(
                        stock_take=stock_take,
                        product_id=product_warehouse.product_id,
                        expected_quantity=product_warehouse.quantity,
                        counted=False
                    )
                    
                    created_items.append(item)
            
            # If no specific products or category, add all products in the warehouse
            else:
                product_warehouses = self.product_warehouse_repository.get_product_warehouses_by_warehouse(
                    warehouse_id=stock_take.warehouse_id
                )
                
                for product_warehouse in product_warehouses:
                    # Create stock take item
                    item = self.stock_take_item_repository.create_item(
                        stock_take=stock_take,
                        product_id=product_warehouse.product_id,
                        expected_quantity=product_warehouse.quantity,
                        counted=False
                    )
                    
                    created_items.append(item)
            
            logger.info(f"Added {len(created_items)} items to stock take {stock_take_id}")
            
            return created_items
            
        except Exception as e:
            logger.error(f"Error adding items to stock take: {str(e)}")
            raise
    
    @transaction.atomic
    def start_stock_take(self, stock_take_id):
        """
        Start a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            The updated stock take
            
        Raises:
            ValueError: If the stock take does not exist or is not in 'planned' status
        """
        try:
            stock_take = self.get_stock_take(stock_take_id)
            
            if stock_take.status != 'planned':
                raise ValueError("Only stock takes in 'planned' status can be started")
            
            # Update stock take status
            stock_take = self.stock_take_repository.update_stock_take(
                stock_take=stock_take,
                status='in_progress',
                start_date=timezone.now().date()
            )
            
            logger.info(f"Stock take {stock_take_id} started")
            
            return stock_take
            
        except Exception as e:
            logger.error(f"Error starting stock take: {str(e)}")
            raise
    
    @transaction.atomic
    def count_item(self, item_id, counted_quantity, counted_by=None, notes=None):
        """
        Count an item in a stock take.
        
        Args:
            item_id: The ID of the stock take item
            counted_quantity: The counted quantity
            counted_by: The user who counted the item (optional)
            notes: Notes for the count (optional)
            
        Returns:
            The updated stock take item
            
        Raises:
            ValueError: If the item does not exist or the stock take is not in 'in_progress' status
        """
        try:
            item = self.get_stock_take_item(item_id)
            
            if item.stock_take.status != 'in_progress':
                raise ValueError("Items can only be counted in stock takes with 'in_progress' status")
            
            # Update item
            item = self.stock_take_item_repository.update_item(
                item=item,
                counted_quantity=counted_quantity,
                counted=True,
                counted_by=counted_by,
                counted_at=timezone.now(),
                notes=notes
            )
            
            logger.info(f"Item {item_id} counted: {counted_quantity}")
            
            return item
            
        except Exception as e:
            logger.error(f"Error counting item: {str(e)}")
            raise
    
    @transaction.atomic
    def complete_stock_take(self, stock_take_id, adjust_stock=True, created_by=None):
        """
        Complete a stock take and optionally adjust stock levels.
        
        Args:
            stock_take_id: The ID of the stock take
            adjust_stock: Whether to adjust stock levels based on counted quantities
            created_by: The user who completed the stock take (optional)
            
        Returns:
            The updated stock take
            
        Raises:
            ValueError: If the stock take does not exist or is not in 'in_progress' status
        """
        try:
            stock_take = self.get_stock_take(stock_take_id)
            
            if stock_take.status != 'in_progress':
                raise ValueError("Only stock takes in 'in_progress' status can be completed")
            
            # Check if all items have been counted
            uncounted_items = self.get_uncounted_items(stock_take_id).count()
            if uncounted_items > 0:
                raise ValueError(f"Cannot complete stock take: {uncounted_items} items have not been counted")
            
            # Adjust stock levels if requested
            if adjust_stock:
                items = self.get_stock_take_items(stock_take_id)
                
                for item in items:
                    # Skip items with no discrepancy
                    if item.expected_quantity == item.counted_quantity:
                        continue
                    
                    # Calculate adjustment
                    adjustment = item.counted_quantity - item.expected_quantity
                    
                    # Skip zero adjustments
                    if adjustment == 0:
                        continue
                    
                    # Create stock movement for adjustment
                    movement_type = 'in' if adjustment > 0 else 'out'
                    quantity = abs(adjustment)
                    
                    self.stock_movement_repository.create_movement(
                        product_id=item.product_id,
                        warehouse_id=stock_take.warehouse_id,
                        quantity=quantity,
                        movement_type=movement_type,
                        reference=f"Stock take adjustment: {stock_take.name}",
                        notes=f"Adjustment from stock take {stock_take.id}",
                        created_by=created_by,
                        created_at=timezone.now()
                    )
                    
                    # Update product warehouse quantity
                    product_warehouse = self.product_warehouse_repository.get_product_warehouse(
                        product_id=item.product_id,
                        warehouse_id=stock_take.warehouse_id
                    )
                    
                    if product_warehouse:
                        product_warehouse.quantity = item.counted_quantity
                        product_warehouse.save()
            
            # Update stock take status
            stock_take = self.stock_take_repository.update_stock_take(
                stock_take=stock_take,
                status='completed',
                end_date=timezone.now().date()
            )
            
            logger.info(f"Stock take {stock_take_id} completed")
            
            return stock_take
            
        except Exception as e:
            logger.error(f"Error completing stock take: {str(e)}")
            raise
    
    @transaction.atomic
    def cancel_stock_take(self, stock_take_id):
        """
        Cancel a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            The updated stock take
            
        Raises:
            ValueError: If the stock take does not exist or is already completed
        """
        try:
            stock_take = self.get_stock_take(stock_take_id)
            
            if stock_take.status == 'completed':
                raise ValueError("Completed stock takes cannot be cancelled")
            
            # Update stock take status
            stock_take = self.stock_take_repository.update_stock_take(
                stock_take=stock_take,
                status='cancelled',
                end_date=timezone.now().date()
            )
            
            logger.info(f"Stock take {stock_take_id} cancelled")
            
            return stock_take
            
        except Exception as e:
            logger.error(f"Error cancelling stock take: {str(e)}")
            raise