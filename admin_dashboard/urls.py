# admin_dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.admin_dashboard, name='admin_dashboard'),

    # Benutzer-Verwaltung
    path('users/', views.user_management, name='admin_user_management'),
    path('users/create/', views.user_create, name='admin_user_create'),
    path('users/<int:user_id>/edit/', views.user_edit, name='admin_user_edit'),
    path('users/<int:user_id>/delete/', views.user_delete, name='admin_user_delete'),
    path('users/<int:user_id>/details/', views.get_user_details, name='admin_get_user_details'),

    # Gruppen-Verwaltung
    path('groups/', views.group_management, name='admin_group_management'),
    path('groups/create/', views.group_create, name='admin_group_create'),
    path('groups/<int:group_id>/edit/', views.group_edit, name='admin_group_edit'),
    path('groups/<int:group_id>/delete/', views.group_delete, name='admin_group_delete'),

    # Abteilungs-Verwaltung
    path('departments/', views.department_management, name='admin_department_management'),
    path('departments/create/', views.department_create, name='admin_department_create'),
    path('departments/<int:department_id>/edit/', views.department_edit, name='admin_department_edit'),
    path('departments/<int:department_id>/delete/', views.department_delete, name='admin_department_delete'),
    path('departments/<int:department_id>/details/', views.get_department_details, name='admin_get_department_details'),

    # Lager-Zugriff
    path('warehouse-access/', views.warehouse_access_management, name='admin_warehouse_access_management'),
    path('warehouse-access/create/', views.warehouse_access_create, name='admin_warehouse_access_create'),
    path('warehouse-access/<int:access_id>/edit/', views.warehouse_access_edit, name='admin_warehouse_access_edit'),
    path('warehouse-access/<int:access_id>/delete/', views.warehouse_access_delete,
         name='admin_warehouse_access_delete'),

    # Systemeinstellungen
    path('system-settings/', views.system_settings, name='admin_system_settings'),

    # Workflow-Einstellungen
    path('workflow-settings/', views.workflow_settings, name='admin_workflow_settings'),
]