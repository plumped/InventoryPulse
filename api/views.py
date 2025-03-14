from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from core.models import (
    Product, Category, ProductWarehouse, ProductPhoto, ProductAttachment,
    ProductVariantType, ProductVariant, SerialNumber, BatchNumber, Tax
)
from suppliers.models import Supplier, SupplierProduct
from inventory.models import Warehouse, StockMovement, StockTake
from order.models import PurchaseOrder, PurchaseOrderItem, OrderSuggestion
from order.workflow import can_approve_order

from .serializers import (
    ProductListSerializer, ProductDetailSerializer, CategorySerializer,
    TaxSerializer, ProductPhotoSerializer, ProductAttachmentSerializer,
    ProductVariantTypeSerializer, ProductVariantSerializer,
    SerialNumberSerializer, BatchNumberSerializer, WarehouseSerializer,
    ProductWarehouseSerializer, StockMovementSerializer, SupplierSerializer,
    SupplierProductSerializer, StockTakeListSerializer,
    PurchaseOrderListSerializer, PurchaseOrderDetailSerializer,
    PurchaseOrderItemSerializer, OrderSuggestionSerializer
)
from .permissions import (
    ProductPermission, InventoryPermission, SupplierPermission,
    OrderPermission, OrderApprovePermission
)


class ProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint for products.
    """
    queryset = Product.objects.all()
    permission_classes = [IsAuthenticated, ProductPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'has_variants', 'has_serial_numbers', 'has_batch_tracking']
    search_fields = ['name', 'sku', 'barcode', 'description']
    ordering_fields = ['name', 'sku', 'category__name', 'minimum_stock']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductDetailSerializer

    @action(detail=True, methods=['get'])
    def variants(self, request, pk=None):
        """Get variants for a specific product"""
        product = self.get_object()
        variants = ProductVariant.objects.filter(parent_product=product)
        serializer = ProductVariantSerializer(variants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def photos(self, request, pk=None):
        """Get photos for a specific product"""
        product = self.get_object()
        photos = ProductPhoto.objects.filter(product=product)
        serializer = ProductPhotoSerializer(photos, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def attachments(self, request, pk=None):
        """Get attachments for a specific product"""
        product = self.get_object()
        attachments = ProductAttachment.objects.filter(product=product)
        serializer = ProductAttachmentSerializer(attachments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def serials(self, request, pk=None):
        """Get serial numbers for a specific product"""
        product = self.get_object()
        serials = SerialNumber.objects.filter(product=product)
        serializer = SerialNumberSerializer(serials, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def batches(self, request, pk=None):
        """Get batch numbers for a specific product"""
        product = self.get_object()
        batches = BatchNumber.objects.filter(product=product)
        serializer = BatchNumberSerializer(batches, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def stock(self, request, pk=None):
        """Get stock information for a specific product"""
        product = self.get_object()
        stocks = ProductWarehouse.objects.filter(product=product)
        serializer = ProductWarehouseSerializer(stocks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        """Get stock movements for a specific product"""
        product = self.get_object()
        movements = StockMovement.objects.filter(product=product).order_by('-created_at')
        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def suppliers(self, request, pk=None):
        """Get suppliers for a specific product"""
        product = self.get_object()
        supplier_products = SupplierProduct.objects.filter(product=product)
        serializer = SupplierProductSerializer(supplier_products, many=True)
        return Response(serializer.data)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for categories.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, ProductPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering = ['name']

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get products in a specific category"""
        category = self.get_object()
        products = Product.objects.filter(category=category)
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)


class TaxViewSet(viewsets.ModelViewSet):
    """
    API endpoint for tax rates.
    """
    queryset = Tax.objects.all()
    serializer_class = TaxSerializer
    permission_classes = [IsAuthenticated, ProductPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_default']
    search_fields = ['name', 'code', 'description']
    ordering = ['rate']


class ProductVariantTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for product variant types.
    """
    queryset = ProductVariantType.objects.all()
    serializer_class = ProductVariantTypeSerializer
    permission_classes = [IsAuthenticated, ProductPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering = ['name']


class ProductVariantViewSet(viewsets.ModelViewSet):
    """
    API endpoint for product variants.
    """
    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated, ProductPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['parent_product', 'variant_type', 'is_active']
    search_fields = ['name', 'sku', 'value', 'barcode']
    ordering = ['parent_product__name', 'name']


class SerialNumberViewSet(viewsets.ModelViewSet):
    """
    API endpoint for serial numbers.
    """
    queryset = SerialNumber.objects.all()
    serializer_class = SerialNumberSerializer
    permission_classes = [IsAuthenticated, ProductPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'variant', 'status', 'warehouse']
    search_fields = ['serial_number', 'notes', 'product__name']
    ordering = ['-created_at']

    @action(detail=False, methods=['get'])
    def scan(self, request):
        """Scan a serial number"""
        serial_number = request.query_params.get('serial_number', None)
        if not serial_number:
            return Response({'error': 'Serial number is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            serial = SerialNumber.objects.get(serial_number=serial_number)
            serializer = self.get_serializer(serial)
            return Response(serializer.data)
        except SerialNumber.DoesNotExist:
            return Response({'error': 'Serial number not found'}, status=status.HTTP_404_NOT_FOUND)


class BatchNumberViewSet(viewsets.ModelViewSet):
    """
    API endpoint for batch numbers.
    """
    queryset = BatchNumber.objects.all()
    serializer_class = BatchNumberSerializer
    permission_classes = [IsAuthenticated, ProductPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'variant', 'warehouse', 'supplier']
    search_fields = ['batch_number', 'notes', 'product__name']
    ordering = ['-created_at']


class WarehouseViewSet(viewsets.ModelViewSet):
    """
    API endpoint for warehouses.
    """
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated, InventoryPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'location', 'description']
    ordering = ['name']

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get products in a specific warehouse"""
        warehouse = self.get_object()
        products = ProductWarehouse.objects.filter(warehouse=warehouse)
        serializer = ProductWarehouseSerializer(products, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        """Get stock movements for a specific warehouse"""
        warehouse = self.get_object()
        movements = StockMovement.objects.filter(warehouse=warehouse).order_by('-created_at')
        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)


class StockMovementViewSet(viewsets.ModelViewSet):
    """
    API endpoint for stock movements.
    """
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated, InventoryPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'warehouse', 'movement_type', 'created_by']
    search_fields = ['reference', 'notes', 'product__name', 'warehouse__name']
    ordering = ['-created_at']


class StockTakeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for stock takes.
    """
    queryset = StockTake.objects.all()
    serializer_class = StockTakeListSerializer
    permission_classes = [IsAuthenticated, InventoryPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['warehouse', 'status', 'inventory_type', 'created_by']
    search_fields = ['name', 'description', 'notes']
    ordering = ['-start_date']


class SupplierViewSet(viewsets.ModelViewSet):
    """
    API endpoint for suppliers.
    """
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, SupplierPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'contact_person', 'email', 'phone', 'address']
    ordering = ['name']

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get products for a specific supplier"""
        supplier = self.get_object()
        supplier_products = SupplierProduct.objects.filter(supplier=supplier)
        serializer = SupplierProductSerializer(supplier_products, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def orders(self, request, pk=None):
        """Get orders for a specific supplier"""
        supplier = self.get_object()
        orders = PurchaseOrder.objects.filter(supplier=supplier)
        serializer = PurchaseOrderListSerializer(orders, many=True)
        return Response(serializer.data)


class SupplierProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint for supplier-product relationships.
    """
    queryset = SupplierProduct.objects.all()
    serializer_class = SupplierProductSerializer
    permission_classes = [IsAuthenticated, SupplierPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier', 'product', 'is_preferred']
    search_fields = ['supplier_sku', 'notes', 'supplier__name', 'product__name']
    ordering = ['supplier__name', 'product__name']


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """
    API endpoint for purchase orders.
    """
    queryset = PurchaseOrder.objects.all()
    permission_classes = [IsAuthenticated, OrderPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier', 'status', 'created_by']
    search_fields = ['order_number', 'notes', 'supplier__name']
    ordering = ['-order_date']

    def get_serializer_class(self):
        if self.action == 'list':
            return PurchaseOrderListSerializer
        return PurchaseOrderDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, OrderApprovePermission])
    def approve(self, request, pk=None):
        """Approve a purchase order"""
        order = self.get_object()

        # Check if the order is pending
        if order.status != 'pending':
            return Response(
                {'error': 'Only pending orders can be approved'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if the user can approve this order
        if not can_approve_order(request.user, order):
            return Response(
                {'error': 'You cannot approve this order because you created it'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Approve the order
        order.status = 'approved'
        order.approved_by = request.user
        order.save()

        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a purchase order"""
        order = self.get_object()

        # Check if the order is pending
        if order.status != 'pending':
            return Response(
                {'error': 'Only pending orders can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )

        rejection_reason = request.data.get('rejection_reason', '')

        # Set order back to draft with rejection reason
        order.status = 'draft'
        order.notes += f"\n\nRejected by {request.user.username}.\nReason: {rejection_reason}"
        order.save()

        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit a purchase order for approval"""
        order = self.get_object()

        # Check if the order is a draft
        if order.status != 'draft':
            return Response(
                {'error': 'Only draft orders can be submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if the order has items
        if not order.items.exists():
            return Response(
                {'error': 'Cannot submit order without any items'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Submit the order
        order.status = 'pending'
        order.save()

        # Check for auto-approval
        from order.workflow import check_auto_approval
        if check_auto_approval(order):
            order.status = 'approved'
            order.approved_by = request.user
            order.save()

        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_sent(self, request, pk=None):
        """Mark a purchase order as sent"""
        order = self.get_object()

        # Check if the order is approved
        if order.status != 'approved':
            return Response(
                {'error': 'Only approved orders can be marked as sent'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark as sent
        order.status = 'sent'
        order.save()

        serializer = self.get_serializer(order)
        return Response(serializer.data)


class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint for purchase order items.
    """
    queryset = PurchaseOrderItem.objects.all()
    serializer_class = PurchaseOrderItemSerializer
    permission_classes = [IsAuthenticated, OrderPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['purchase_order', 'product']
    search_fields = ['supplier_sku', 'item_notes', 'product__name']
    ordering = ['purchase_order__order_number', 'product__name']


class OrderSuggestionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for order suggestions.
    """
    queryset = OrderSuggestion.objects.all()
    serializer_class = OrderSuggestionSerializer
    permission_classes = [IsAuthenticated, OrderPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'preferred_supplier']
    search_fields = ['product__name', 'product__sku', 'preferred_supplier__name']
    ordering = ['product__name']

    @action(detail=False, methods=['post'])
    def refresh(self, request):
        """Refresh order suggestions"""
        from order.services import generate_order_suggestions

        try:
            count = generate_order_suggestions()
            return Response({'message': f'{count} order suggestions generated', 'count': count})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)