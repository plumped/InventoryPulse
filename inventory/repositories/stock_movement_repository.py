"""
Repository for StockMovement model.

This module contains the StockMovementRepository class that handles all data access
operations related to the StockMovement model.
"""

from django.db.models import Q

from .base import BaseRepository
from ..models import StockMovement


class StockMovementRepository(BaseRepository):
    """Repository for StockMovement model."""
    
    model_class = StockMovement
    
    def get_movement_by_id(self, movement_id):
        """
        Get a stock movement by its ID.
        
        Args:
            movement_id: The ID of the stock movement
            
        Returns:
            The stock movement with the given ID
            
        Raises:
            StockMovement.DoesNotExist: If the stock movement does not exist
        """
        return self.get_by_id(movement_id)
    
    def get_movements_by_warehouse(self, warehouse_id):
        """
        Get all stock movements for a warehouse.
        
        Args:
            warehouse_id: The ID of the warehouse
            
        Returns:
            QuerySet of stock movements for the warehouse
        """
        return self.filter(warehouse_id=warehouse_id).order_by('-created_at')
    
    def get_movements_by_product(self, product_id):
        """
        Get all stock movements for a product.
        
        Args:
            product_id: The ID of the product
            
        Returns:
            QuerySet of stock movements for the product
        """
        return self.filter(product_id=product_id).order_by('-created_at')
    
    def get_movements_by_type(self, movement_type):
        """
        Get all stock movements of a specific type.
        
        Args:
            movement_type: The type of stock movement ('in', 'out', 'transfer', etc.)
            
        Returns:
            QuerySet of stock movements of the specified type
        """
        return self.filter(movement_type=movement_type).order_by('-created_at')
    
    def search_movements(self, search_query):
        """
        Search for stock movements by reference or notes.
        
        Args:
            search_query: The search query
            
        Returns:
            QuerySet of matching stock movements
        """
        if not search_query:
            return self.all().order_by('-created_at')
            
        query = Q(reference__icontains=search_query) | \
                Q(notes__icontains=search_query) | \
                Q(product__name__icontains=search_query)
                
        return self.filter_with_q(query).order_by('-created_at')
    
    def filter_movements(self, warehouse_id=None, product_id=None, movement_type=None, 
                         date_from=None, date_to=None, search_query=None):
        """
        Filter stock movements by various criteria.
        
        Args:
            warehouse_id: The ID of the warehouse
            product_id: The ID of the product
            movement_type: The type of stock movement
            date_from: The start date for filtering
            date_to: The end date for filtering
            search_query: The search query for reference, notes, or product name
            
        Returns:
            QuerySet of filtered stock movements
        """
        movements = self.all()
        
        if warehouse_id:
            movements = movements.filter(warehouse_id=warehouse_id)
        
        if product_id:
            movements = movements.filter(product_id=product_id)
        
        if movement_type:
            movements = movements.filter(movement_type=movement_type)
        
        if date_from:
            movements = movements.filter(created_at__gte=date_from)
        
        if date_to:
            movements = movements.filter(created_at__lte=date_to)
        
        if search_query:
            query = Q(reference__icontains=search_query) | \
                    Q(notes__icontains=search_query) | \
                    Q(product__name__icontains=search_query)
            movements = movements.filter(query)
        
        return movements.order_by('-created_at')
    
    def create_movement(self, **kwargs):
        """
        Create a new stock movement.
        
        Args:
            **kwargs: Stock movement attributes
            
        Returns:
            The created stock movement
        """
        return self.create(**kwargs)