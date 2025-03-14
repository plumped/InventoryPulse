from rest_framework import serializers
from core.models import (
    Product, Category, ProductWarehouse, ProductPhoto, ProductAttachment,
    ProductVariantType, ProductVariant, SerialNumber, BatchNumber, Tax
)
from suppliers.models import Supplier, SupplierProduct
from inventory.models import Warehouse, StockMovement, StockTake
from order.models import PurchaseOrder, PurchaseOrderItem, OrderSuggestion


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class TaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tax
        fields = ['id', 'name', 'code', 'rate', 'description', 'is_default', 'is_active']


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'barcode', 'category', 'category_name', 'minimum_stock']


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tax = TaxSerializer(read_only=True)
    total_stock = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'barcode', 'description', 'category', 'tax',
            'minimum_stock', 'unit', 'has_variants', 'has_serial_numbers',
            'has_batch_tracking', 'has_expiry_tracking', 'total_stock'
        ]


class ProductPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductPhoto
        fields = ['id', 'product', 'image', 'is_primary', 'caption', 'upload_date']


class ProductAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttachment
        fields = ['id', 'product', 'file', 'title', 'description', 'file_type', 'upload_date']


class ProductVariantTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariantType
        fields = ['id', 'name', 'description']


class ProductVariantSerializer(serializers.ModelSerializer):
    variant_type_name = serializers.ReadOnlyField(source='variant_type.name')

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'parent_product', 'sku', 'name', 'variant_type', 'variant_type_name',
            'value', 'price_adjustment', 'barcode', 'is_active'
        ]


class SerialNumberSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    warehouse_name = serializers.ReadOnlyField(source='warehouse.name')
    variant_name = serializers.ReadOnlyField(source='variant.name')
    status_display = serializers.ReadOnlyField(source='get_status_display')

    class Meta:
        model = SerialNumber
        fields = [
            'id', 'product', 'product_name', 'variant', 'variant_name', 'serial_number',
            'status', 'status_display', 'purchase_date', 'expiry_date', 'notes',
            'warehouse', 'warehouse_name', 'created_at', 'updated_at'
        ]


class BatchNumberSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    warehouse_name = serializers.ReadOnlyField(source='warehouse.name')
    supplier_name = serializers.ReadOnlyField(source='supplier.name')

    class Meta:
        model = BatchNumber
        fields = [
            'id', 'product', 'product_name', 'variant', 'batch_number', 'quantity',
            'production_date', 'expiry_date', 'supplier', 'supplier_name',
            'warehouse', 'warehouse_name', 'notes', 'created_at'
        ]


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'location', 'description', 'is_active']


class ProductWarehouseSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    warehouse_name = serializers.ReadOnlyField(source='warehouse.name')

    class Meta:
        model = ProductWarehouse
        fields = ['id', 'product', 'product_name', 'warehouse', 'warehouse_name', 'quantity']


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    warehouse_name = serializers.ReadOnlyField(source='warehouse.name')
    created_by_username = serializers.ReadOnlyField(source='created_by.username')
    movement_type_display = serializers.ReadOnlyField(source='get_movement_type_display')

    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'warehouse', 'warehouse_name',
            'quantity', 'movement_type', 'movement_type_display', 'reference',
            'notes', 'created_by', 'created_by_username', 'created_at'
        ]


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'contact_person', 'email', 'phone', 'address',
            'shipping_cost', 'minimum_order_value', 'is_active'
        ]


class SupplierProductSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source='supplier.name')
    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = SupplierProduct
        fields = [
            'id', 'supplier', 'supplier_name', 'product', 'product_name',
            'supplier_sku', 'purchase_price', 'lead_time_days', 'is_preferred',
            'notes'
        ]


class StockTakeListSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.ReadOnlyField(source='warehouse.name')
    created_by_username = serializers.ReadOnlyField(source='created_by.username')
    completed_by_username = serializers.ReadOnlyField(source='completed_by.username')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    completion_percentage = serializers.ReadOnlyField(source='get_completion_percentage')

    class Meta:
        model = StockTake
        fields = [
            'id', 'name', 'status', 'status_display', 'warehouse', 'warehouse_name',
            'inventory_type', 'start_date', 'end_date', 'created_by', 'created_by_username',
            'completed_by', 'completed_by_username', 'completion_percentage'
        ]


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    line_total = serializers.ReadOnlyField()
    receipt_status = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id', 'purchase_order', 'product', 'product_name', 'quantity_ordered',
            'quantity_received', 'unit_price', 'supplier_sku', 'item_notes',
            'tax_rate', 'line_total', 'receipt_status'
        ]


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source='supplier.name')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    created_by_username = serializers.ReadOnlyField(source='created_by.username')

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'order_number', 'supplier', 'supplier_name', 'order_date',
            'status', 'status_display', 'total', 'created_by', 'created_by_username'
        ]


class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    supplier = SupplierSerializer(read_only=True)
    created_by_username = serializers.ReadOnlyField(source='created_by.username')
    approved_by_username = serializers.ReadOnlyField(source='approved_by.username')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'order_number', 'supplier', 'order_date', 'expected_delivery',
            'status', 'status_display', 'created_by', 'created_by_username',
            'approved_by', 'approved_by_username', 'shipping_address', 'notes',
            'subtotal', 'tax', 'shipping_cost', 'total', 'items'
        ]


class OrderSuggestionSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    product_sku = serializers.ReadOnlyField(source='product.sku')
    preferred_supplier_name = serializers.ReadOnlyField(source='preferred_supplier.name')

    class Meta:
        model = OrderSuggestion
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'current_stock',
            'minimum_stock', 'suggested_order_quantity', 'preferred_supplier',
            'preferred_supplier_name', 'last_calculated'
        ]