from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from . import views

# Schema-Beschreibung für die API-Dokumentation
schema_view = get_schema_view(
    openapi.Info(
        title="InventoryPulse API",
        default_version='v1',
        description="API für das InventoryPulse Warenwirtschaftssystem",
        terms_of_service="",
        contact=openapi.Contact(email="admin@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.IsAuthenticated,),
)

# Router für die API-Endpunkte konfigurieren
router = DefaultRouter()
router.register(r'products', views.ProductViewSet)
router.register(r'categories', views.CategoryViewSet)
router.register(r'taxes', views.TaxViewSet)
router.register(r'variant-types', views.ProductVariantTypeViewSet)
router.register(r'variants', views.ProductVariantViewSet)
router.register(r'serials', views.SerialNumberViewSet)
router.register(r'batches', views.BatchNumberViewSet)
router.register(r'warehouses', views.WarehouseViewSet)
router.register(r'stock-movements', views.StockMovementViewSet)
router.register(r'stock-takes', views.StockTakeViewSet)
router.register(r'suppliers', views.SupplierViewSet)
router.register(r'supplier-products', views.SupplierProductViewSet)
router.register(r'purchase-orders', views.PurchaseOrderViewSet)
router.register(r'purchase-order-items', views.PurchaseOrderItemViewSet)
router.register(r'order-suggestions', views.OrderSuggestionViewSet)

urlpatterns = [
    # API-Endpunkte
    path('', include(router.urls)),

    # API-Dokumentation
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Auth-URLs für browsable API
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]