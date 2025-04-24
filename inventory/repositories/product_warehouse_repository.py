"""
Repository for ProductWarehouse model.

This module contains the ProductWarehouseRepository class that handles all data access
operations related to the ProductWarehouse model.
"""

from django.db.models import Q, Sum, F

from product_management.models.products_models import ProductWarehouse
from .base import BaseRepository


class ProductWarehouseRepository(BaseRepository):
    """Repository for ProductWarehouse model."""
    
    model_class = ProductWarehouse
    
    def get_product_warehouse_by_id(self, product_warehouse_id):
        """
        Get a product warehouse by its ID.
        
        Args:
            product_warehouse_id: The ID of the product warehouse
            
        Returns:
            The product warehouse with the given ID
            
        Raises:
            ProductWarehouse.DoesNotExist: If the product warehouse does not exist
        """
        return self.get_by_id(product_warehouse_id)
    
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
        return self.get(product_id=product_id, warehouse_id=warehouse_id)
    
    def get_product_warehouses_by_product(self, product_id):
        """
        Get all warehouses for a product.
        
        Args:
            product_id: The ID of the product
            
        Returns:
            QuerySet of product warehouses for the product
        """
        return self.filter(product_id=product_id)
    
    def get_product_warehouses_by_warehouse(self, warehouse_id):
        """
        Get all products in a warehouse.
        
        Args:
            warehouse_id: The ID of the warehouse
            
        Returns:
            QuerySet of product warehouses for the warehouse
        """
        return self.filter(warehouse_id=warehouse_id)
    
    def get_products_with_stock(self, warehouse_id):
        """
        Get all products with stock in a warehouse.
        
        Args:
            warehouse_id: The ID of the warehouse
            
        Returns:
            QuerySet of product warehouses with stock > 0
        """
        return self.filter(warehouse_id=warehouse_id, quantity__gt=0)
    
    def get_products_with_low_stock(self, warehouse_id=None):
        """
        Get all products with low stock.
        
        Args:
            warehouse_id: The ID of the warehouse (optional)
            
        Returns:
            QuerySet of product warehouses with stock below minimum level
        """
        query = Q(quantity__lt=F('product__minimum_stock'))
        
        if warehouse_id:
            query &= Q(warehouse_id=warehouse_id)
            
        return self.filter_with_q(query)
    
    def get_total_stock_for_product(self, product_id):
        """
        Get the total stock for a product across all warehouses.
        
        Args:
            product_id: The ID of the product
            
        Returns:
            The total stock for the product
        """
        result = self.filter(product_id=product_id).aggregate(total=Sum('quantity'))
        return result['total'] or 0
    
    def create_product_warehouse(self, **kwargs):
        """
        Create a new product warehouse.
        
        Args:
            **kwargs: Product warehouse attributes
            
        Returns:
            The created product warehouse
        """
        return self.create(**kwargs)
    
    def update_product_warehouse(self, product_warehouse, **kwargs):
        """
        Update an existing product warehouse.
        
        Args:
            product_warehouse: The product warehouse to update
            **kwargs: Attributes to update
            
        Returns:
            The updated product warehouse
        """
        return self.update(product_warehouse, **kwargs)
    
    def delete_product_warehouse(self, product_warehouse):
        """
        Delete a product warehouse.
        
        Args:
            product_warehouse: The product warehouse to delete
        """
        self.delete(product_warehouse)
    
    def update_quantity(self, product_id, warehouse_id, quantity_change):
        """
        Update the quantity of a product in a warehouse.
        
        Args:
            product_id: The ID of the product
            warehouse_id: The ID of the warehouse
            quantity_change: The change in quantity (positive or negative)
            
        Returns:
            The updated product warehouse
            
        Raises:
            ProductWarehouse.DoesNotExist: If the product warehouse does not exist
        """
        product_warehouse = self.get(product_id=product_id, warehouse_id=warehouse_id)
        product_warehouse.quantity += quantity_change
        product_warehouse.save()
        return product_warehouse
    
    def get_or_create_product_warehouse(self, product_id, warehouse_id, default_quantity=0):
        """
        Get or create a product warehouse.
        
        Args:
            product_id: The ID of the product
            warehouse_id: The ID of the warehouse
            default_quantity: The default quantity if creating a new product warehouse
            
        Returns:
            Tuple of (product_warehouse, created) where created is a boolean
            indicating whether a new product warehouse was created
        """
        try:
            product_warehouse = self.get(product_id=product_id, warehouse_id=warehouse_id)
            return product_warehouse, False
        except ProductWarehouse.DoesNotExist:
            product_warehouse = self.create(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=default_quantity
            )
            return product_warehouse, True