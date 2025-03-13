# accessmanagement/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Warehouse access management
    path('warehouse-access/', views.warehouse_access_management, name='warehouse_access_management'),
    path('warehouse-access/add/', views.warehouse_access_add, name='warehouse_access_add'),
    path('warehouse-access/<int:pk>/edit/', views.warehouse_access_edit, name='warehouse_access_edit'),
    path('warehouse-access/<int:pk>/delete/', views.warehouse_access_delete, name='warehouse_access_delete'),
    
    # User permissions management
    path('permissions/', views.user_permissions_management, name='user_permissions_management'),
    path('permissions/user/', views.get_user_permissions, name='get_user_permissions'),
]