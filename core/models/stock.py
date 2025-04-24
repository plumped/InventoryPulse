"""
Stock-related models for the core app.

This module contains models related to stock management that are used across multiple apps in the project.
"""

from django.contrib.auth.models import User
from django.db import models

from core.models.warehouse import Warehouse


class BaseStockMovement(models.Model):
    """
    Base model for stock movements.
    
    This is an abstract base class that provides common fields and functionality for stock movements.
    It is used by both the inventory and product_management apps.
    """
    MOVEMENT_TYPE_CHOICES = [
        ('in', 'In'),
        ('out', 'Out'),
        ('adj', 'Adjustment'),
        ('transfer', 'Transfer'),
    ]
    
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name="Warehouse")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Quantity")
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPE_CHOICES, verbose_name="Movement Type")
    reference = models.CharField(max_length=255, blank=True, verbose_name="Reference")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Created By")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    
    class Meta:
        abstract = True
        ordering = ['-created_at']
        verbose_name = "Stock Movement"
        verbose_name_plural = "Stock Movements"


class BaseProductWarehouse(models.Model):
    """
    Base model for product-warehouse relationships.
    
    This is an abstract base class that provides common fields and functionality for product-warehouse relationships.
    It is used by both the inventory and product_management apps.
    """
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name="Warehouse")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Quantity")
    
    class Meta:
        abstract = True
        verbose_name = "Product Warehouse"
        verbose_name_plural = "Product Warehouses"