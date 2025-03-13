from django.urls import path
from . import views

urlpatterns = [
    path('', views.supplier_list, name='supplier_list'),
    path('create/', views.supplier_create, name='supplier_create'),
    path('<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('<int:pk>/update/', views.supplier_update, name='supplier_update'),
    path('product/add/', views.supplier_product_add, name='supplier_product_add'),
    path('product/<int:pk>/update/', views.supplier_product_update, name='supplier_product_update'),
    path('product/<int:pk>/delete/', views.supplier_product_delete, name='supplier_product_delete'),

    path('get-supplier-data/', views.get_supplier_data, name='get_supplier_data'),
]