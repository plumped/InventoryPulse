from django.urls import path, include

from tracking.views.batch_views import (
    product_batches, product_batch_add, product_batch_update, product_batch_delete,
    batch_number_list, batch_number_detail, batch_number_add, batch_number_edit,
    batch_number_delete, batch_number_scan, batch_number_transfer, batch_number_import,
    batch_number_export
)
from tracking.views.expiry_views import expiry_management
from tracking.views.serial_views import (
    product_serials, product_serial_add, product_serial_delete,
    product_serial_update, product_serial_bulk_add, serialnumber_list,
    serialnumber_add, serialnumber_transfer, serialnumber_import, serialnumber_export,
    serialnumber_scan, serialnumber_search, serialnumber_batch_actions,
    serialnumber_detail, serialnumber_history
)

urlpatterns = [
    # Seriennummernverwaltung - global
    path('serialnumbers/', include([
        path('', serialnumber_list, name='serialnumber_list'),
        path('add/', serialnumber_add, name='serialnumber_add'),
        path('transfer/', serialnumber_transfer, name='serialnumber_transfer'),
        path('import/', serialnumber_import, name='serialnumber_import'),
        path('export/', serialnumber_export, name='serialnumber_export'),
        path('scan/', serialnumber_scan, name='serialnumber_scan'),
        path('search/', serialnumber_search, name='serialnumber_search'),
        path('batch-actions/', serialnumber_batch_actions, name='serialnumber_batch_actions'),
        path('<int:serial_id>/', serialnumber_detail, name='serialnumber_detail'),
        path('<int:serial_id>/history/', serialnumber_history, name='serialnumber_history'),
    ])),

    # Chargennummernverwaltung - global
    path('batch-numbers/', include([
        path('', batch_number_list, name='batch_number_list'),
        path('add/', batch_number_add, name='batch_number_add'),
        path('scan/', batch_number_scan, name='batch_number_scan'),
        path('transfer/', batch_number_transfer, name='batch_number_transfer'),
        path('import/', batch_number_import, name='batch_number_import'),
        path('export/', batch_number_export, name='batch_number_export'),
        path('<int:batch_id>/', batch_number_detail, name='batch_number_detail'),
        path('<int:batch_id>/edit/', batch_number_edit, name='batch_number_edit'),
        path('<int:batch_id>/delete/', batch_number_delete, name='batch_number_delete'),
    ])),

    # Ablaufverwaltung
    path('expiry-management/', expiry_management, name='expiry_management'),

    # Produktspezifische Seriennummern
    path('products/<int:pk>/serials/', include([
        path('', product_serials, name='product_serials'),
        path('add/', product_serial_add, name='product_serial_add'),
        path('bulk-add/', product_serial_bulk_add, name='product_serial_bulk_add'),
        path('<int:serial_id>/update/', product_serial_update, name='product_serial_update'),
        path('<int:serial_id>/delete/', product_serial_delete, name='product_serial_delete'),
    ])),

    # Produktspezifische Chargen
    path('products/<int:pk>/batches/', include([
        path('', product_batches, name='product_batches'),
        path('add/', product_batch_add, name='product_batch_add'),
        path('<int:batch_id>/update/', product_batch_update, name='product_batch_update'),
        path('<int:batch_id>/delete/', product_batch_delete, name='product_batch_delete'),
    ])),
]
