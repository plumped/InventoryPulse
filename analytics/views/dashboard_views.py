import logging

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

logger = logging.getLogger('analytics')


@login_required
def dashboard(request):
    logger.debug(f"Dashboard view accessed by user {request.user.username} (ID: {request.user.id})")

    # Existierende Daten
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_suppliers = Supplier.objects.count()

    logger.debug(f"Dashboard counts - Products: {total_products}, Categories: {total_categories}, Suppliers: {total_suppliers}")

    # Lager, auf die der Benutzer Zugriff hat
    if request.user.is_superuser:
        logger.debug(f"User {request.user.username} is superuser, getting all active warehouses")
        accessible_warehouses = Warehouse.objects.filter(is_active=True)
        logger.debug(f"Type of accessible_warehouses: {type(accessible_warehouses)}, Count: {accessible_warehouses.count()}")
    else:
        logger.debug(f"User {request.user.username} is not superuser, filtering warehouses by access")
        all_warehouses = Warehouse.objects.filter(is_active=True)
        logger.debug(f"Total active warehouses: {all_warehouses.count()}")

        accessible_warehouses = [w for w in all_warehouses if WarehouseAccess.has_access(request.user, w, 'view')]
        logger.debug(f"Type of accessible_warehouses: {type(accessible_warehouses)}, Length: {len(accessible_warehouses)}")
        logger.debug(f"Accessible warehouse IDs: {[w.id for w in accessible_warehouses]}")

    try:
        logger.debug("Attempting to generate order suggestions")
        from order.services import generate_order_suggestions
        generate_order_suggestions()
        logger.debug("Order suggestions generated successfully")
    except ImportError as e:
        logger.warning(f"Could not import generate_order_suggestions: {str(e)}")
        pass  # Ignorieren, falls die Funktion nicht importiert werden kann
    except Exception as e:
        logger.error(f"Error generating order suggestions: {str(e)}")
        pass  # Andere Fehler abfangen

    # Produkte mit niedrigem Bestand basierend auf zugänglichen Lagern
    try:
        logger.debug(f"Calculating low stock products based on accessible warehouses")
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
        logger.debug(f"Found {low_stock_count} products with low stock")
    except Exception as e:
        logger.error(f"Error calculating low stock products: {str(e)}")
        low_stock_products = Product.objects.none()
        low_stock_count = 0

    # Neue Daten für Lager und Abteilungen
    try:
        logger.debug(f"Calculating total warehouses. Type of accessible_warehouses: {type(accessible_warehouses)}")
        if isinstance(accessible_warehouses, list):
            total_warehouses = len(accessible_warehouses)
            logger.debug(f"accessible_warehouses is a list, using len(): {total_warehouses}")
        else:
            total_warehouses = accessible_warehouses.count()
            logger.debug(f"accessible_warehouses is a QuerySet, using count(): {total_warehouses}")

        total_departments = Department.objects.count()
        logger.debug(f"Total departments: {total_departments}")

        active_stock_takes_count = StockTake.objects.filter(status='in_progress').count()
        logger.debug(f"Active stock takes: {active_stock_takes_count}")
    except Exception as e:
        logger.error(f"Error calculating totals: {str(e)}")
        total_warehouses = 0
        total_departments = 0
        active_stock_takes_count = 0

    # Erweiterte Daten für Tabellen
    try:
        logger.debug("Fetching recent stock movements")
        recent_movements = StockMovement.objects.select_related('product', 'warehouse', 'created_by').order_by(
            '-created_at')[:10]
        logger.debug(f"Found {len(recent_movements)} recent stock movements")
    except Exception as e:
        logger.error(f"Error fetching recent stock movements: {str(e)}")
        recent_movements = []

    # Kritische Bestände nach Lager
    try:
        logger.debug("Calculating low stock products detail")
        low_stock_products_detail = []

        # Define ProductWarehouseInfo class for both cases
        class ProductWarehouseInfo:
            def __init__(self, product, warehouse, quantity):
                self.product = product
                self.warehouse = warehouse
                self.quantity = quantity

        for product in low_stock_products[:10]:  # Limit auf 10 Produkte
            logger.debug(f"Processing low stock product: {product.name} (ID: {product.id})")

            try:
                # Finde das Lager mit dem größten Bestand für dieses Produkt
                main_warehouse = ProductWarehouse.objects.filter(
                    product=product,
                    warehouse__in=accessible_warehouses
                ).order_by('-quantity').first()

                if main_warehouse:
                    logger.debug(f"Found main warehouse for product {product.name}: {main_warehouse.warehouse.name} with quantity {main_warehouse.quantity}")

                    # Verwende das Dummy-Objekt statt main_warehouse direkt
                    product_warehouse_info = ProductWarehouseInfo(
                        product=product,
                        warehouse=main_warehouse.warehouse,
                        quantity=main_warehouse.quantity
                    )
                else:
                    logger.debug(f"No warehouse found for product {product.name}, creating entry with quantity 0")

                    product_warehouse_info = ProductWarehouseInfo(
                        product=product,
                        warehouse=None,
                        quantity=0
                    )

                low_stock_products_detail.append(product_warehouse_info)
            except Exception as e:
                logger.error(f"Error processing low stock product {product.name}: {str(e)}")
                # Continue with next product

        logger.debug(f"Processed {len(low_stock_products_detail)} low stock products")
    except Exception as e:
        logger.error(f"Error calculating low stock products detail: {str(e)}")
        low_stock_products_detail = []

    # Ersetze low_stock_items durch unsere neue Liste
    low_stock_items = low_stock_products_detail

    # Aktive Inventuren
    try:
        logger.debug("Fetching active stock takes")
        active_stock_takes = StockTake.objects.select_related('warehouse').filter(status='in_progress')[:5]
        logger.debug(f"Found {len(active_stock_takes)} active stock takes")
    except Exception as e:
        logger.error(f"Error fetching active stock takes: {str(e)}")
        active_stock_takes = []

    # Lagerübersicht mit Produktanzahl
    try:
        logger.debug("Calculating product counts for warehouses")
        warehouses = accessible_warehouses

        # If warehouses is a QuerySet, convert to list to avoid modifying the QuerySet
        if not isinstance(warehouses, list):
            logger.debug("Converting warehouses QuerySet to list")
            warehouses = list(warehouses)

        for warehouse in warehouses:
            try:
                product_count = ProductWarehouse.objects.filter(warehouse=warehouse, quantity__gt=0).count()
                warehouse.product_count = product_count
                logger.debug(f"Warehouse {warehouse.name} (ID: {warehouse.id}) has {product_count} products")
            except Exception as e:
                logger.error(f"Error calculating product count for warehouse {warehouse.name}: {str(e)}")
                warehouse.product_count = 0
    except Exception as e:
        logger.error(f"Error processing warehouses: {str(e)}")
        warehouses = []

    # Order statistics
    try:
        logger.debug("Calculating order statistics")
        pending_count = PurchaseOrder.objects.filter(status='pending').count()
        sent_count = PurchaseOrder.objects.filter(status='sent').count()
        partial_count = PurchaseOrder.objects.filter(status='partially_received').count()
        suggestion_count = OrderSuggestion.objects.count()

        logger.debug(f"Order statistics - Pending: {pending_count}, Sent: {sent_count}, Partial: {partial_count}, Suggestions: {suggestion_count}")
    except Exception as e:
        logger.error(f"Error calculating order statistics: {str(e)}")
        pending_count = 0
        sent_count = 0
        partial_count = 0
        suggestion_count = 0

    # Letzte Bestellungen
    try:
        logger.debug("Fetching recent orders")
        recent_orders = PurchaseOrder.objects.select_related('supplier').order_by('-order_date')[:5]
        logger.debug(f"Found {len(recent_orders)} recent orders")
    except Exception as e:
        logger.error(f"Error fetching recent orders: {str(e)}")
        recent_orders = []

    # Prepare context for template
    try:
        logger.debug("Preparing context for template rendering")
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
            'warehouses': warehouses[:5] if len(warehouses) > 5 else warehouses,
            'pending_count': pending_count,
            'sent_count': sent_count,
            'partial_count': partial_count,
            'suggestion_count': suggestion_count,
            'recent_orders': recent_orders,
        }

        # Log key metrics for monitoring
        logger.info(
            f"Dashboard metrics - Products: {total_products}, Low Stock: {low_stock_count}, "
            f"Warehouses: {total_warehouses}, Departments: {total_departments}, "
            f"Active Stock Takes: {active_stock_takes_count}"
        )

        logger.debug("Rendering dashboard template")
        return render(request, 'dashboard.html', context)
    except Exception as e:
        logger.error(f"Error rendering dashboard: {str(e)}")
        # Provide a minimal context in case of error
        error_context = {
            'error_message': "An error occurred while preparing the dashboard. Please try again later."
        }
        return render(request, 'error/500.html', error_context)
