from django.urls import path
from . import views

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

    # AJAX-Endpunkt für Lieferantenproduktpreis
    path('get-supplier-product-price/', views.get_supplier_product_price, name='get_supplier_product_price'),
    path('bulk-send/', views.bulk_send_orders, name='bulk_send_orders'),

]