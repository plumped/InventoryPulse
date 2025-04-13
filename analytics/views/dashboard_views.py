from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, F, Sum
from django.db.models.expressions import Subquery, OuterRef, Value
from django.db.models.functions import Coalesce
from django.shortcuts import render

from accessmanagement.models import WarehouseAccess
from inventory.models import StockTake, StockMovement, Warehouse
from master_data.models.organisations_models import Department
from order.models import PurchaseOrder, OrderSuggestion
from product_management.models.categories_models import Category
from product_management.models.products_models import ProductWarehouse, Product
from suppliers.models import Supplier


@login_required
def dashboard(request):
    # Existierende Daten
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_suppliers = Supplier.objects.count()

    # Lager, auf die der Benutzer Zugriff hat
    if request.user.is_superuser:
        accessible_warehouses = Warehouse.objects.filter(is_active=True)
    else:
        accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                                 if WarehouseAccess.has_access(request.user, w, 'view')]

    try:
        from order.services import generate_order_suggestions
        generate_order_suggestions()
    except ImportError:
        pass  # Ignorieren, falls die Funktion nicht importiert werden kann

    # Produkte mit niedrigem Bestand basierend auf zugänglichen Lagern
    low_stock_products = Product.objects.annotate(
        accessible_stock=Coalesce(
            Subquery(
                ProductWarehouse.objects.filter(
                    product=OuterRef('pk'),
                    warehouse__in=accessible_warehouses  # Korrekte Variable verwenden
                ).values('product')
                .annotate(total=Sum('quantity'))
                .values('total')[:1]
            ),
            Value(0, output_field=DecimalField(max_digits=10, decimal_places=2))  # DecimalField statt FloatField
        )
    ).filter(
        accessible_stock__lt=F('minimum_stock')
    )

    low_stock_count = low_stock_products.count()

    # Neue Daten für Lager und Abteilungen
    total_warehouses = accessible_warehouses.count()
    total_departments = Department.objects.count()
    active_stock_takes_count = StockTake.objects.filter(status='in_progress').count()

    # Erweiterte Daten für Tabellen
    recent_movements = StockMovement.objects.select_related('product', 'warehouse', 'created_by').order_by(
        '-created_at')[:10]

    # Kritische Bestände nach Lager
    low_stock_products_detail = []
    for product in low_stock_products[:10]:  # Limit auf 10 Produkte
        # Finde das Lager mit dem größten Bestand für dieses Produkt
        main_warehouse = ProductWarehouse.objects.filter(
            product=product,
            warehouse__in=accessible_warehouses
        ).order_by('-quantity').first()

        if main_warehouse:
            # Erstelle ein Dummy-Objekt mit den benötigten Eigenschaften
            class ProductWarehouseInfo:
                def __init__(self, product, warehouse, quantity):
                    self.product = product
                    self.warehouse = warehouse
                    self.quantity = quantity

            # Verwende das Dummy-Objekt statt main_warehouse direkt
            product_warehouse_info = ProductWarehouseInfo(
                product=product,
                warehouse=main_warehouse.warehouse,
                quantity=main_warehouse.quantity
            )

            low_stock_products_detail.append(product_warehouse_info)
        else:
            # Wenn kein Lager gefunden wurde, erstelle einen Eintrag mit Menge 0
            class ProductWarehouseInfo:
                def __init__(self, product, warehouse, quantity):
                    self.product = product
                    self.warehouse = None
                    self.quantity = quantity

            product_warehouse_info = ProductWarehouseInfo(
                product=product,
                warehouse=None,
                quantity=0
            )

            low_stock_products_detail.append(product_warehouse_info)

    # Ersetze low_stock_items durch unsere neue Liste
    low_stock_items = low_stock_products_detail

    # Aktive Inventuren
    active_stock_takes = StockTake.objects.select_related('warehouse').filter(status='in_progress')[:5]

    # Lagerübersicht mit Produktanzahl
    warehouses = accessible_warehouses
    for warehouse in warehouses:
        warehouse.product_count = ProductWarehouse.objects.filter(warehouse=warehouse, quantity__gt=0).count()

    pending_count = PurchaseOrder.objects.filter(status='pending').count()
    sent_count = PurchaseOrder.objects.filter(status='sent').count()
    partial_count = PurchaseOrder.objects.filter(status='partially_received').count()
    suggestion_count = OrderSuggestion.objects.count()

    # Letzte Bestellungen
    recent_orders = PurchaseOrder.objects.select_related('supplier').order_by('-order_date')[:5]

    context = {
        'total_products': total_products,
        'total_categories': total_categories,
        'total_suppliers': total_suppliers,
        'low_stock_count': low_stock_count,
        'total_warehouses': total_warehouses,
        'total_departments': total_departments,
        'active_stock_takes_count': active_stock_takes_count,
        'recent_movements': recent_movements,
        'low_stock_items': low_stock_items,
        'active_stock_takes': active_stock_takes,
        'warehouses': warehouses[:5],
        'pending_count': pending_count,
        'sent_count': sent_count,
        'partial_count': partial_count,
        'suggestion_count': suggestion_count,
        'recent_orders': recent_orders,
    }

    return render(request, 'dashboard.html', context)
