from django.urls import path
from . import views

urlpatterns = [
    # Schnittstellen-Management
    path('', views.interface_list, name='interface_list'),
    path('<int:pk>/', views.interface_detail, name='interface_detail'),
    path('create/', views.interface_create, name='interface_create'),
    path('<int:pk>/update/', views.interface_update, name='interface_update'),
    path('<int:pk>/delete/', views.interface_delete, name='interface_delete'),
    path('<int:pk>/toggle-active/', views.interface_toggle_active, name='interface_toggle_active'),
    path('<int:pk>/set-default/', views.interface_set_default, name='interface_set_default'),
    path('<int:pk>/test/', views.test_interface, name='test_interface'),
    
    # Übertragungsprotokolle
    path('logs/', views.interface_logs, name='interface_logs'),
    path('logs/<int:pk>/', views.interface_log_detail, name='interface_log_detail'),
    path('logs/<int:log_id>/retry/', views.retry_failed_transmission, name='retry_failed_transmission'),
    
    # Schnittstellen für Lieferanten
    path('supplier/<int:supplier_id>/', views.interface_list, name='supplier_interfaces'),
    
    # Bestellungsversand
    path('order/<int:order_id>/send/', views.send_order, name='send_order'),
    path('order/<int:order_id>/select-interface/', views.select_interface, name='select_interface'),
    
    # AJAX-Endpunkte
    path('api/get-supplier-interfaces/', views.get_supplier_interfaces, name='get_supplier_interfaces'),
    path('api/get-interface-fields/', views.get_interface_fields, name='get_interface_fields'),
]