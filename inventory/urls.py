from django.urls import path
from . import views

urlpatterns = [
    # Bestandsbewegungen
    path('movements/', views.stock_movement_list, name='stock_movement_list'),
    
    # Inventur
    path('stock-takes/', views.stock_take_list, name='stock_take_list'),
    path('stock-takes/create/', views.stock_take_create, name='stock_take_create'),
    path('stock-takes/<int:pk>/', views.stock_take_detail, name='stock_take_detail'),
    path('stock-takes/<int:pk>/update/', views.stock_take_update, name='stock_take_update'),
    path('stock-takes/<int:pk>/delete/', views.stock_take_delete, name='stock_take_delete'),
    path('stock-takes/<int:pk>/start/', views.stock_take_start, name='stock_take_start'),
    path('stock-takes/<int:pk>/complete/', views.stock_take_complete, name='stock_take_complete'),
    path('stock-takes/<int:pk>/cancel/', views.stock_take_cancel, name='stock_take_cancel'),
    path('stock-takes/<int:pk>/count-items/', views.stock_take_count_items, name='stock_take_count_items'),
    path('stock-takes/<int:pk>/barcode-scan/', views.stock_take_barcode_scan, name='stock_take_barcode_scan'),
    path('stock-takes/<int:pk>/report/', views.stock_take_report, name='stock_take_report'),
    path('stock-takes/<int:pk>/export-csv/', views.stock_take_export_csv, name='stock_take_export_csv'),
    path('stock-takes/<int:pk>/export-pdf/', views.stock_take_export_pdf, name='stock_take_export_pdf'),
    path('stock-takes/<int:pk>/items/<int:item_id>/count/', views.stock_take_item_count, name='stock_take_item_count'),
    path('stock-takes/<int:pk>/create-cycle/', views.stock_take_create_cycle, name='stock_take_create_cycle'),


    # Lagerverwaltung
    path('warehouses/', views.warehouse_list, name='warehouse_list'),
    path('warehouses/create/', views.warehouse_create, name='warehouse_create'),
    path('warehouses/<int:pk>/', views.warehouse_detail, name='warehouse_detail'),
    path('warehouses/<int:pk>/update/', views.warehouse_update, name='warehouse_update'),
    path('warehouses/<int:pk>/delete/', views.warehouse_delete, name='warehouse_delete'),

    # Abteilungsverwaltung
    path('departments/', views.department_management, name='department_management'),
    path('departments/create/', views.department_create, name='department_create'),
    path('departments/<int:pk>/update/', views.department_update, name='department_update'),
    path('departments/<int:pk>/delete/', views.department_delete, name='department_delete'),
    path('departments/<int:pk>/members/', views.department_members, name='department_members'),
    path('departments/<int:pk>/add-member/', views.department_add_member, name='department_add_member'),
    path('departments/<int:pk>/edit-member/<int:member_id>/', views.department_edit_member, name='department_edit_member'),
    path('departments/<int:pk>/remove-member/<int:member_id>/', views.department_remove_member, name='department_remove_member'),

    # Lagerzugriffsrechte
    path('warehouse-access/', views.warehouse_access_management, name='warehouse_access_management'),
    path('warehouse-access/add/', views.warehouse_access_add, name='warehouse_access_add'),
    path('warehouse-access/<int:pk>/update/', views.warehouse_access_update, name='warehouse_access_update'),
    path('warehouse-access/<int:pk>/delete/', views.warehouse_access_delete, name='warehouse_access_delete'),

    # Produktbestandsverwaltung
    path('products/<int:product_id>/warehouses/', views.product_warehouses, name='product_warehouses'),
    path('products/add-to-warehouse/<int:warehouse_id>/', views.product_add_to_warehouse, name='product_add_to_warehouse'),
    path('warehouses/<int:warehouse_id>/bulk-add-products/', views.bulk_add_products_to_warehouse, name='bulk_add_products_to_warehouse'),
    path('warehouses/bulk-transfer/', views.bulk_warehouse_transfer, name='bulk_warehouse_transfer'),


]