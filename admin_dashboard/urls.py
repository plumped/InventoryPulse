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

    path('company-addresses/', views.company_address_management, name='admin_company_address_management'),
    path('company-addresses/create/', views.company_address_create, name='admin_company_address_create'),
    path('company-addresses/<int:address_id>/edit/', views.company_address_edit, name='admin_company_address_edit'),
    path('company-addresses/<int:address_id>/delete/', views.company_address_delete, name='admin_company_address_delete'),

    # Systemeinstellungen
    path('system-settings/', views.system_settings, name='admin_system_settings'),

    # Workflow-Einstellungen
    path('workflow-settings/', views.workflow_settings, name='admin_workflow_settings'),

    path('taxes/', views.tax_management, name='admin_tax_management'),
    path('taxes/create/', views.tax_create, name='admin_tax_create'),
    path('taxes/<int:tax_id>/edit/', views.tax_edit, name='admin_tax_edit'),
    path('taxes/<int:tax_id>/delete/', views.tax_delete, name='admin_tax_delete'),

    path('interfaces/', views.interface_management, name='admin_interface_management'),
    path('interfaces/types/', views.interface_type_management, name='admin_interface_type_management'),
    path('interfaces/types/create/', views.interface_type_create, name='admin_interface_type_create'),
    path('interfaces/types/<int:type_id>/edit/', views.interface_type_edit, name='admin_interface_type_edit'),
    path('interfaces/types/<int:type_id>/delete/', views.interface_type_delete, name='admin_interface_type_delete'),
]