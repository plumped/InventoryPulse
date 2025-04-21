# admin_dashboard/urls.py
from django.urls import path, include

from master_data.views.currency_views import currency_list, currency_create, currency_update, currency_delete
from . import permission_views
from . import predefined_role_views
from . import views

urlpatterns = [
    # Dashboard
    path('', views.admin_dashboard, name='admin_dashboard'),

    path('currencies/', include([
        path('', currency_list, name='currency_list'),
        path('create/', currency_create, name='currency_create'),
        path('<int:pk>/update/', currency_update, name='currency_update'),
        path('<int:pk>/delete/', currency_delete, name='currency_delete'),
    ])),

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

    # Dokumenttypen-Verwaltung
    path('document-types/', views.document_type_management, name='admin_document_type_management'),
    path('document-types/create/', views.document_type_create, name='admin_document_type_create'),
    path('document-types/<int:type_id>/edit/', views.document_type_edit, name='admin_document_type_edit'),
    path('document-types/<int:type_id>/delete/', views.document_type_delete, name='admin_document_type_delete'),
    path('document-types/setup-standard-fields/', views.setup_standard_fields, name='setup_standard_fields'),

    # Admin Menu
    path('menu/', views.admin_menu, name='admin_menu'),

    # Permissions Management
    path('permissions/', include([
        path('', permission_views.permissions_dashboard, name='admin_permissions_dashboard'),
        path('user/<int:user_id>/', permission_views.user_permissions, name='admin_user_permissions'),
        path('object/', permission_views.object_permissions, name='admin_object_permissions'),
        path('object/add/', permission_views.object_permission_add, name='admin_object_permission_add'),
        path('object/<int:pk>/edit/', permission_views.object_permission_edit, name='admin_object_permission_edit'),
        path('object/<int:pk>/delete/', permission_views.object_permission_delete, name='admin_object_permission_delete'),
        path('role-hierarchy/', permission_views.role_hierarchy, name='admin_role_hierarchy'),
        path('role-hierarchy/add/', permission_views.role_hierarchy_add, name='admin_role_hierarchy_add'),
        path('role-hierarchy/<int:pk>/edit/', permission_views.role_hierarchy_edit, name='admin_role_hierarchy_edit'),
        path('role-hierarchy/<int:pk>/delete/', permission_views.role_hierarchy_delete, name='admin_role_hierarchy_delete'),
        path('time-based/', permission_views.time_based_permissions, name='admin_time_based_permissions'),
        path('time-based/add/', permission_views.time_based_permission_add, name='admin_time_based_permission_add'),
        path('time-based/<int:pk>/edit/', permission_views.time_based_permission_edit, name='admin_time_based_permission_edit'),
        path('time-based/<int:pk>/delete/', permission_views.time_based_permission_delete, name='admin_time_based_permission_delete'),
        path('audit/', permission_views.permission_audit, name='admin_permission_audit'),
        path('audit/run/', permission_views.run_permission_audit, name='admin_run_permission_audit'),
        path('audit/download/<str:filename>/', permission_views.download_report, name='admin_download_report'),
        path('audit/view/<str:filename>/', permission_views.view_report, name='admin_view_report'),
        path('warehouse-access/', permission_views.warehouse_access, name='admin_warehouse_access'),
        path('warehouse-access/add/', permission_views.warehouse_access_add, name='admin_warehouse_access_add'),
        path('warehouse-access/<int:pk>/edit/', permission_views.warehouse_access_edit, name='admin_warehouse_access_edit'),
        path('warehouse-access/<int:pk>/delete/', permission_views.warehouse_access_delete, name='admin_warehouse_access_delete'),
        path('predefined-roles/', predefined_role_views.predefined_roles, name='admin_predefined_roles'),
        path('predefined-roles/create-all/', predefined_role_views.create_all_predefined_roles_view, name='admin_create_all_predefined_roles'),
        path('predefined-roles/create/', predefined_role_views.create_predefined_role_view, name='admin_create_predefined_role'),
        path('get-objects-for-content-type/', permission_views.get_objects_for_content_type, name='admin_get_objects_for_content_type'),
    ])),
]
