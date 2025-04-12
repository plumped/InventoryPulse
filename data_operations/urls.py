from django.urls import path, include

# Imports besser organisiert und alphabetisch sortiert
from data_operations.views.export_views import export_import_logs
from data_operations.views.import_views import (
    import_dashboard,
    import_categories,
    import_departments,
    import_products,
    import_serialnumbers,
    import_suppliers,
    import_supplier_products,
    import_warehouses,
    import_warehouse_products,
)
from data_operations.views.log_views import (
    bulk_delete_import_logs,
    delete_import_log,
    download_error_file,
    import_log_detail,
    import_log_list,
)

# Die Import-URLs selbst - besser strukturiert mit Gruppierung
urlpatterns = [
    path('import/', include([
        # Dashboard
        path('', import_dashboard, name='import_dashboard'),

        # Hauptimportfunktionen - alphabetisch sortiert
        path('categories/', import_categories, name='import_categories'),
        path('departments/', import_departments, name='import_departments'),
        path('products/', import_products, name='import_products'),
        path('serialnumbers/', import_serialnumbers, name='import_serialnumbers'),
        path('suppliers/', import_suppliers, name='import_suppliers'),
        path('supplier-products/', import_supplier_products, name='import_supplier_products'),
        path('warehouses/', import_warehouses, name='import_warehouses'),
        path('warehouse-products/', import_warehouse_products, name='import_warehouse_products'),

        # Log-Management als eigene Gruppe mit Unterrouten
        path('logs/', include([
            path('', import_log_list, name='import_log_list'),
            path('<int:pk>/', import_log_detail, name='import_log_detail'),
            path('<int:log_id>/delete/', delete_import_log, name='delete_import_log'),
            path('<int:log_id>/download-errors/', download_error_file, name='download_error_file'),
            path('bulk-delete/', bulk_delete_import_logs, name='bulk_delete_import_logs'),
            path('export/', export_import_logs, name='export_import_logs'),
        ])),
    ])),
]
