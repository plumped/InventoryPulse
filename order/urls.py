from django.urls import path
from . import views
from .batch_processor import (
    batch_order_import_view,
    download_order_template,
    batch_order_import_result,
    download_error_report
)

urlpatterns = [
    # Bestellungsübersicht
    path('', views.purchase_order_list, name='purchase_order_list'),

    # Detailansicht einer Bestellung
    path('<int:pk>/', views.purchase_order_detail, name='purchase_order_detail'),

    # Neue Bestellung erstellen
    path('create/', views.purchase_order_create, name='purchase_order_create'),

    # Bestellung bearbeiten
    path('<int:pk>/update/', views.purchase_order_update, name='purchase_order_update'),

    # Bestellung löschen
    path('<int:pk>/delete/', views.purchase_order_delete, name='purchase_order_delete'),

    # Bestellung zur Genehmigung einreichen
    path('<int:pk>/submit/', views.purchase_order_submit, name='purchase_order_submit'),

    # Bestellung genehmigen
    path('<int:pk>/approve/', views.purchase_order_approve, name='purchase_order_approve'),

    # Bestellung ablehnen
    path('<int:pk>/reject/', views.purchase_order_reject, name='purchase_order_reject'),

    # Wareneingang erfassen
    path('<int:pk>/receive/', views.purchase_order_receive, name='purchase_order_receive'),
    path('<int:pk>/receive/<int:split_id>/', views.purchase_order_receive, name='purchase_order_receive_split'),

    # Wareneingang bearbeiten
    path('<int:pk>/receipt/<int:receipt_id>/edit/', views.purchase_order_receipt_edit, name='purchase_order_receipt_edit'),

    # Wareneingang löschen
    path('<int:pk>/receipt/<int:receipt_id>/delete/', views.purchase_order_receipt_delete, name='purchase_order_receipt_delete'),

    # Bestellung drucken
    path('<int:pk>/print/', views.purchase_order_print, name='purchase_order_print'),

    # Bestellung exportieren
    path('<int:pk>/export/', views.purchase_order_export, name='purchase_order_export'),

    # Bestellvorschläge
    path('suggestions/', views.order_suggestions, name='order_suggestions'),

    # Bestellvorschläge aktualisieren
    path('suggestions/refresh/', views.refresh_order_suggestions, name='refresh_order_suggestions'),

    # Bestellungen aus Vorschlägen erstellen
    path('suggestions/create-orders/', views.create_orders_from_suggestions, name='create_orders_from_suggestions'),

    path('templates/', views.order_template_list, name='order_template_list'),
    path('templates/create/', views.order_template_create, name='order_template_create'),
    path('templates/<int:pk>/', views.order_template_detail, name='order_template_detail'),
    path('templates/<int:pk>/update/', views.order_template_update, name='order_template_update'),
    path('templates/<int:pk>/delete/', views.order_template_delete, name='order_template_delete'),
    path('templates/<int:pk>/toggle-active/', views.order_template_toggle_active, name='order_template_toggle_active'),
    path('templates/<int:pk>/duplicate/', views.order_template_duplicate, name='order_template_duplicate'),
    path('templates/<int:pk>/create-order/', views.create_order_from_template, name='create_order_from_template'),
    path('batch-import/', batch_order_import_view, name='batch_order_import'),
    path('batch-import/result/', batch_order_import_result, name='batch_order_import_result'),
    path('batch-template/<str:format_type>/', download_order_template, name='download_order_template'),
    path('batch-errors/<str:format_type>/', download_error_report, name='download_error_report'),
    path('<int:pk>/item/<int:item_id>/cancel/', views.purchase_order_item_cancel, name='purchase_order_item_cancel'),
    path('<int:pk>/item/<int:item_id>/edit-cancellation/', views.purchase_order_item_edit_cancellation, name='purchase_order_item_edit_cancellation'),

    path('<int:pk>/splits/', views.order_split_list, name='order_split_list'),
    path('<int:pk>/splits/create/', views.order_split_create, name='order_split_create'),
    path('<int:pk>/splits/<int:split_id>/', views.order_split_detail, name='order_split_detail'),
    path('<int:pk>/splits/<int:split_id>/edit/', views.order_split_update, name='order_split_update'),
    path('<int:pk>/splits/<int:split_id>/delete/', views.order_split_delete, name='order_split_delete'),
    path('<int:pk>/splits/<int:split_id>/receive/', views.receive_order_split, name='receive_order_split'),
    path('<int:pk>/splits/<int:split_id>/status/', views.order_split_update_status, name='order_split_update_status'),
    # AJAX-Endpunkt für Lieferantenproduktpreis
    path('get-supplier-product-price/', views.get_supplier_product_price, name='get_supplier_product_price'),
    path('get-supplier-products-list/', views.get_supplier_products_list, name='get_supplier_products_list'),
    path('bulk-send/', views.bulk_send_orders, name='bulk_send_orders'),
    path('<int:pk>/splits/check/', views.check_order_splits, name='check_order_splits'),
    path('<int:pk>/comments/', views.purchase_order_comments, name='purchase_order_comments'),
    path('<int:pk>/comments/add/', views.add_order_comment, name='add_order_comment'),
    path('<int:pk>/comments/<int:comment_id>/delete/', views.delete_order_comment, name='delete_order_comment'),

]