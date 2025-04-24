"""
Repository for StockTake model.

This module contains the StockTakeRepository class that handles all data access
operations related to the StockTake model.
"""

from django.db.models import Q

from .base import BaseRepository
from ..models import StockTake, StockTakeItem


class StockTakeRepository(BaseRepository):
    """Repository for StockTake model."""
    
    model_class = StockTake
    
    def get_stock_take_by_id(self, stock_take_id):
        """
        Get a stock take by its ID.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            The stock take with the given ID
            
        Raises:
            StockTake.DoesNotExist: If the stock take does not exist
        """
        return self.get_by_id(stock_take_id)
    
    def get_stock_takes_by_warehouse(self, warehouse_id):
        """
        Get all stock takes for a warehouse.
        
        Args:
            warehouse_id: The ID of the warehouse
            
        Returns:
            QuerySet of stock takes for the warehouse
        """
        return self.filter(warehouse_id=warehouse_id).order_by('-start_date')
    
    def get_stock_takes_by_status(self, status):
        """
        Get all stock takes with a specific status.
        
        Args:
            status: The status of the stock take ('planned', 'in_progress', 'completed', 'cancelled')
            
        Returns:
            QuerySet of stock takes with the specified status
        """
        return self.filter(status=status).order_by('-start_date')
    
    def get_stock_takes_by_type(self, inventory_type):
        """
        Get all stock takes of a specific type.
        
        Args:
            inventory_type: The type of stock take ('full', 'partial', 'rolling', etc.)
            
        Returns:
            QuerySet of stock takes of the specified type
        """
        return self.filter(inventory_type=inventory_type).order_by('-start_date')
    
    def search_stock_takes(self, search_query):
        """
        Search for stock takes by name, description, or notes.
        
        Args:
            search_query: The search query
            
        Returns:
            QuerySet of matching stock takes
        """
        if not search_query:
            return self.all().order_by('-start_date')
            
        query = Q(name__icontains=search_query) | \
                Q(description__icontains=search_query) | \
                Q(notes__icontains=search_query)
                
        return self.filter_with_q(query).order_by('-start_date')
    
    def filter_stock_takes(self, warehouse_id=None, status=None, inventory_type=None, 
                           date_from=None, date_to=None, search_query=None):
        """
        Filter stock takes by various criteria.
        
        Args:
            warehouse_id: The ID of the warehouse
            status: The status of the stock take
            inventory_type: The type of stock take
            date_from: The start date for filtering
            date_to: The end date for filtering
            search_query: The search query for name, description, or notes
            
        Returns:
            QuerySet of filtered stock takes
        """
        stock_takes = self.all()
        
        if warehouse_id:
            stock_takes = stock_takes.filter(warehouse_id=warehouse_id)
        
        if status:
            stock_takes = stock_takes.filter(status=status)
        
        if inventory_type:
            stock_takes = stock_takes.filter(inventory_type=inventory_type)
        
        if date_from:
            stock_takes = stock_takes.filter(start_date__gte=date_from)
        
        if date_to:
            stock_takes = stock_takes.filter(start_date__lte=date_to)
        
        if search_query:
            query = Q(name__icontains=search_query) | \
                    Q(description__icontains=search_query) | \
                    Q(notes__icontains=search_query)
            stock_takes = stock_takes.filter(query)
        
        return stock_takes.order_by('-start_date')
    
    def create_stock_take(self, **kwargs):
        """
        Create a new stock take.
        
        Args:
            **kwargs: Stock take attributes
            
        Returns:
            The created stock take
        """
        return self.create(**kwargs)
    
    def update_stock_take(self, stock_take, **kwargs):
        """
        Update an existing stock take.
        
        Args:
            stock_take: The stock take to update
            **kwargs: Attributes to update
            
        Returns:
            The updated stock take
        """
        return self.update(stock_take, **kwargs)
    
    def delete_stock_take(self, stock_take):
        """
        Delete a stock take.
        
        Args:
            stock_take: The stock take to delete
        """
        self.delete(stock_take)


class StockTakeItemRepository(BaseRepository):
    """Repository for StockTakeItem model."""
    
    model_class = StockTakeItem
    
    def get_item_by_id(self, item_id):
        """
        Get a stock take item by its ID.
        
        Args:
            item_id: The ID of the stock take item
            
        Returns:
            The stock take item with the given ID
            
        Raises:
            StockTakeItem.DoesNotExist: If the stock take item does not exist
        """
        return self.get_by_id(item_id)
    
    def get_items_by_stock_take(self, stock_take_id):
        """
        Get all items for a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            QuerySet of items for the stock take
        """
        return self.filter(stock_take_id=stock_take_id)
    
    def get_items_by_product(self, product_id):
        """
        Get all stock take items for a product.
        
        Args:
            product_id: The ID of the product
            
        Returns:
            QuerySet of stock take items for the product
        """
        return self.filter(product_id=product_id)
    
    def get_uncounted_items(self, stock_take_id):
        """
        Get all uncounted items for a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            QuerySet of uncounted items for the stock take
        """
        return self.filter(stock_take_id=stock_take_id, counted=False)
    
    def get_counted_items(self, stock_take_id):
        """
        Get all counted items for a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            QuerySet of counted items for the stock take
        """
        return self.filter(stock_take_id=stock_take_id, counted=True)
    
    def get_discrepancy_items(self, stock_take_id):
        """
        Get all items with discrepancies for a stock take.
        
        Args:
            stock_take_id: The ID of the stock take
            
        Returns:
            QuerySet of items with discrepancies for the stock take
        """
        return self.filter(
            stock_take_id=stock_take_id, 
            counted=True
        ).exclude(expected_quantity=F('counted_quantity'))
    
    def create_item(self, **kwargs):
        """
        Create a new stock take item.
        
        Args:
            **kwargs: Stock take item attributes
            
        Returns:
            The created stock take item
        """
        return self.create(**kwargs)
    
    def update_item(self, item, **kwargs):
        """
        Update an existing stock take item.
        
        Args:
            item: The stock take item to update
            **kwargs: Attributes to update
            
        Returns:
            The updated stock take item
        """
        return self.update(item, **kwargs)
    
    def delete_item(self, item):
        """
        Delete a stock take item.
        
        Args:
            item: The stock take item to delete
        """
        self.delete(item)