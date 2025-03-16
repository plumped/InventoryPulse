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
    path('test-connectivity/', views.test_interface_connectivity, name='test_interface_connectivity'),
    path('test-send-order/', views.test_send_order, name='test_send_order'),



    # Übertragungsprotokolle
    path('logs/', views.interface_logs, name='interface_logs'),
    path('logs/for-interface/<int:interface_id>/', views.interface_logs, name='interface_logs_filtered'),
    # Changed URL pattern
    path('log/<int:pk>/', views.interface_log_detail, name='interface_log_detail'),  # Changed URL pattern
    path('log/<int:log_id>/retry/', views.retry_failed_transmission, name='retry_failed_transmission'),
    # Should also change for consistency
    
    # Schnittstellen für Lieferanten
    path('supplier/<int:supplier_id>/', views.interface_list, name='supplier_interfaces'),
    
    # Bestellungsversand
    path('order/<int:order_id>/send/', views.send_order, name='send_order'),
    
    # AJAX-Endpunkte
    path('api/get-supplier-interfaces/', views.get_supplier_interfaces, name='get_supplier_interfaces'),
    path('api/get-interface-fields/', views.get_interface_fields, name='get_interface_fields'),
    path('xml-templates/', views.list_xml_templates, name='list_xml_templates'),
    path('xml-templates/<int:template_id>/', views.xml_template_detail, name='xml_template_detail'),

    # AJAX-Endpunkte für XML-Vorlagen
    path('api/get-xml-template/<int:template_id>/', views.get_xml_template, name='get_xml_template'),
    path('api/preview-xml-template/', views.preview_xml_template, name='preview_xml_template'),
]