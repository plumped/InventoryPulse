"""
Warehouse model for the core app.

This module contains the Warehouse model, which is used across multiple apps in the project.
"""

from django.db import models


class Warehouse(models.Model):
    """
    Warehouse model for storing information about physical warehouses.
    
    This model is used by multiple apps in the project, including inventory and product_management.
    """
    name = models.CharField(max_length=100, verbose_name="Name")
    location = models.CharField(max_length=200, verbose_name="Location")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    code = models.CharField(max_length=20, unique=True, verbose_name="Code", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Warehouse"
        verbose_name_plural = "Warehouses"
        ordering = ['name']