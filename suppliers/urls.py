# Update the suppliers/urls.py file to include our new views

from django.urls import path
from . import views

urlpatterns = [
    # Existing URL patterns from suppliers/urls.py
    path('', views.supplier_list, name='supplier_list'),
    path('create/', views.supplier_create, name='supplier_create'),
    path('<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('<int:pk>/update/', views.supplier_update, name='supplier_update'),

    path('<int:supplier_id>/address/add/', views.supplier_address_create, name='supplier_address_create'),
    path('address/<int:pk>/update/', views.supplier_address_update, name='supplier_address_update'),
    path('address/<int:pk>/delete/', views.supplier_address_delete, name='supplier_address_delete'),

    path('<int:supplier_id>/contact/add/', views.supplier_contact_create, name='supplier_contact_create'),
    path('contact/<int:pk>/update/', views.supplier_contact_update, name='supplier_contact_update'),
    path('contact/<int:pk>/delete/', views.supplier_contact_delete, name='supplier_contact_delete'),

    path('product/add/', views.supplier_product_add, name='supplier_product_add'),
    path('product/<int:pk>/update/', views.supplier_product_update, name='supplier_product_update'),
    path('product/<int:pk>/delete/', views.supplier_product_delete, name='supplier_product_delete'),
    path('get-supplier-data/', views.get_supplier_data, name='get_supplier_data'),
    path('get-supplier-products/', views.get_supplier_products, name='get_supplier_products'),

    # New URL patterns for supplier performance tracking
    path('performance/', views.supplier_performance_overview, name='supplier_performance_overview'),
    path('performance/<int:pk>/', views.supplier_performance_detail, name='supplier_performance_detail'),
    path('performance/<int:supplier_id>/add/', views.supplier_performance_add, name='supplier_performance_add'),
    path('performance/edit/<int:pk>/', views.supplier_performance_edit, name='supplier_performance_edit'),
    path('performance/delete/<int:pk>/', views.supplier_performance_delete, name='supplier_performance_delete'),
    path('performance/<int:supplier_id>/calculate/', views.supplier_performance_calculate,
         name='supplier_performance_calculate'),

    # Performance metric management
    path('performance/metrics/', views.supplier_performance_metrics_list, name='supplier_performance_metrics_list'),
    path('performance/metrics/create/', views.supplier_performance_metric_create,
         name='supplier_performance_metric_create'),
    path('performance/metrics/<int:pk>/edit/', views.supplier_performance_metric_edit,
         name='supplier_performance_metric_edit'),
    path('performance/metrics/<int:pk>/delete/', views.supplier_performance_metric_delete,
         name='supplier_performance_metric_delete'),

    # AJAX endpoint for chart data
    path('performance/<int:supplier_id>/data/', views.get_supplier_performance_data,
         name='get_supplier_performance_data'),
    path('get-supplier-addresses/', views.get_supplier_addresses, name='get_supplier_addresses'),
    path('get-supplier-contacts/', views.get_supplier_contacts, name='get_supplier_contacts'),
    path('get-supplier-rma-info/', views.get_supplier_rma_info, name='get_supplier_rma_info'),
]