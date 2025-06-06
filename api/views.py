from django.contrib.auth.models import User
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from core.models import (
    Product, Category, ProductWarehouse, ProductPhoto, ProductAttachment,
    ProductVariantType, ProductVariant, SerialNumber, BatchNumber, Tax
)
from core.utils.api_helpers import generate_related_action
from inventory.models import Warehouse, StockMovement, StockTake
from order.models import PurchaseOrder, PurchaseOrderItem, OrderSuggestion
from order.workflow import can_approve_order
from suppliers.models import Supplier, SupplierProduct
from .serializers import (
    ProductListSerializer, ProductDetailSerializer, CategorySerializer,
    TaxSerializer, ProductPhotoSerializer, ProductAttachmentSerializer,
    ProductVariantTypeSerializer, ProductVariantSerializer,
    SerialNumberSerializer, BatchNumberSerializer, WarehouseSerializer,
    ProductWarehouseSerializer, StockMovementSerializer, SupplierSerializer,
    SupplierProductSerializer, StockTakeListSerializer,
    PurchaseOrderListSerializer, PurchaseOrderDetailSerializer,
    PurchaseOrderItemSerializer, OrderSuggestionSerializer, UserSerializer
)


class ReadOnlyPermission(permissions.BasePermission):
    """
    Erlaubt nur Lesezugriff (GET, HEAD, OPTIONS)
    """

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'has_variants', 'has_serial_numbers', 'has_batch_tracking']
    search_fields = ['name', 'sku', 'barcode', 'description']
    ordering_fields = ['name', 'sku', 'category__name', 'minimum_stock']
    ordering = ['name']

    def get_serializer_class(self):
        return ProductListSerializer if self.action == 'list' else ProductDetailSerializer

    @action(detail=True, methods=['get'])
    def variants(self, request, pk=None):
        return generate_related_action(self, ProductVariant, ProductVariantSerializer, 'parent_product')

    @action(detail=True, methods=['get'])
    def photos(self, request, pk=None):
        return generate_related_action(self, ProductPhoto, ProductPhotoSerializer)

    @action(detail=True, methods=['get'])
    def attachments(self, request, pk=None):
        return generate_related_action(self, ProductAttachment, ProductAttachmentSerializer)

    @action(detail=True, methods=['get'])
    def serials(self, request, pk=None):
        return generate_related_action(self, SerialNumber, SerialNumberSerializer)

    @action(detail=True, methods=['get'])
    def batches(self, request, pk=None):
        return generate_related_action(self, BatchNumber, BatchNumberSerializer)

    @action(detail=True, methods=['get'])
    def stock(self, request, pk=None):
        return generate_related_action(self, ProductWarehouse, ProductWarehouseSerializer)

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        return generate_related_action(self, StockMovement, StockMovementSerializer, order_by='-created_at')

    @action(detail=True, methods=['get'])
    def suppliers(self, request, pk=None):
        return generate_related_action(self, SupplierProduct, SupplierProductSerializer)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering = ['name']

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        return generate_related_action(self, Product, ProductListSerializer, 'category')


class TaxViewSet(viewsets.ModelViewSet):
    queryset = Tax.objects.all()
    serializer_class = TaxSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_default']
    search_fields = ['name', 'code', 'description']
    ordering = ['rate']


class ProductVariantTypeViewSet(viewsets.ModelViewSet):
    queryset = ProductVariantType.objects.all()
    serializer_class = ProductVariantTypeSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering = ['name']


class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['parent_product', 'variant_type', 'is_active']
    search_fields = ['name', 'sku', 'value', 'barcode']
    ordering = ['parent_product__name', 'name']


class SerialNumberViewSet(viewsets.ModelViewSet):
    queryset = SerialNumber.objects.all()
    serializer_class = SerialNumberSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'variant', 'status', 'warehouse']
    search_fields = ['serial_number', 'notes', 'product__name']
    ordering = ['-created_at']

    @action(detail=False, methods=['get'])
    def scan(self, request):
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
    queryset = BatchNumber.objects.all()
    serializer_class = BatchNumberSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'variant', 'warehouse', 'supplier']
    search_fields = ['batch_number', 'notes', 'product__name']
    ordering = ['-created_at']


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'location', 'description']
    ordering = ['name']

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        return generate_related_action(self, ProductWarehouse, ProductWarehouseSerializer, 'warehouse')

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        return generate_related_action(self, StockMovement, StockMovementSerializer, 'warehouse',
                                       order_by='-created_at')


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'warehouse', 'movement_type', 'created_by']
    search_fields = ['reference', 'notes', 'product__name', 'warehouse__name']
    ordering = ['-created_at']


class StockTakeViewSet(viewsets.ModelViewSet):
    queryset = StockTake.objects.all()
    serializer_class = StockTakeListSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['warehouse', 'status', 'inventory_type', 'created_by']
    search_fields = ['name', 'description', 'notes']
    ordering = ['-start_date']


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'contact_person', 'email', 'phone', 'address']
    ordering = ['name']

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        return generate_related_action(self, SupplierProduct, SupplierProductSerializer, 'supplier')

    @action(detail=True, methods=['get'])
    def orders(self, request, pk=None):
        return generate_related_action(self, PurchaseOrder, PurchaseOrderListSerializer, 'supplier')


class SupplierProductViewSet(viewsets.ModelViewSet):
    queryset = SupplierProduct.objects.all()
    serializer_class = SupplierProductSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier', 'product', 'is_preferred']
    search_fields = ['supplier_sku', 'notes', 'supplier__name', 'product__name']
    ordering = ['supplier__name', 'product__name']


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all()
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier', 'status', 'created_by']
    search_fields = ['order_number', 'notes', 'supplier__name']
    ordering = ['-order_date']

    def get_serializer_class(self):
        return PurchaseOrderListSerializer if self.action == 'list' else PurchaseOrderDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, DjangoModelPermissions])
    def approve(self, request, pk=None):
        order = self.get_object()
        if order.status != 'pending':
            return Response({'error': 'Only pending orders can be approved'}, status=status.HTTP_400_BAD_REQUEST)
        if not can_approve_order(request.user, order):
            return Response({'error': 'You cannot approve this order because you created it'},
                            status=status.HTTP_403_FORBIDDEN)
        order.status = 'approved'
        order.approved_by = request.user
        order.save()
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        order = self.get_object()
        if order.status != 'pending':
            return Response({'error': 'Only pending orders can be rejected'}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get('rejection_reason', '')
        order.status = 'draft'
        order.notes += f"\n\nRejected by {request.user.username}.\nReason: {reason}"
        order.save()
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        order = self.get_object()
        if order.status != 'draft':
            return Response({'error': 'Only draft orders can be submitted'}, status=status.HTTP_400_BAD_REQUEST)
        if not order.items.exists():
            return Response({'error': 'Cannot submit order without any items'}, status=status.HTTP_400_BAD_REQUEST)
        order.status = 'pending'
        order.save()
        from order.workflow import check_auto_approval
        if check_auto_approval(order):
            order.status = 'approved'
            order.approved_by = request.user
            order.save()
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=['post'])
    def mark_sent(self, request, pk=None):
        order = self.get_object()
        if order.status != 'approved':
            return Response({'error': 'Only approved orders can be marked as sent'}, status=status.HTTP_400_BAD_REQUEST)
        order.status = 'sent'
        order.save()
        return Response(self.get_serializer(order).data)


class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrderItem.objects.all()
    serializer_class = PurchaseOrderItemSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['purchase_order', 'product']
    search_fields = ['supplier_sku', 'item_notes', 'product__name']
    ordering = ['purchase_order__order_number', 'product__name']


class OrderSuggestionViewSet(viewsets.ModelViewSet):
    queryset = OrderSuggestion.objects.all()
    serializer_class = OrderSuggestionSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'preferred_supplier']
    search_fields = ['product__name', 'product__sku', 'preferred_supplier__name']
    ordering = ['product__name']

    @action(detail=False, methods=['post'])
    def refresh(self, request):
        from order.services import generate_order_suggestions
        try:
            count = generate_order_suggestions()
            return Response({'message': f'{count} order suggestions generated', 'count': count})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['username', 'date_joined', 'last_login', 'first_name', 'last_name']
    ordering = ['username']

    def get_queryset(self):
        qs = User.objects.all()
        return qs.filter(is_active=True) if not self.request.user.is_superuser else qs

    @action(detail=True, methods=['get'])
    def departments(self, request, pk=None):
        user = self.get_object()
        try:
            departments = user.profile.departments.all()
            return Response([{'id': d.id, 'name': d.name, 'code': d.code} for d in departments])
        except AttributeError:
            return Response([])

    @action(detail=True, methods=['get'])
    def groups(self, request, pk=None):
        user = self.get_object()
        return Response([{'id': g.id, 'name': g.name} for g in user.groups.all()])
