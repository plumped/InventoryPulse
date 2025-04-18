from django.urls import path

from . import views

app_name = 'superadmin'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Module Management
    path('modules/', views.module_list, name='module_list'),
    path('modules/<int:module_id>/', views.module_detail, name='module_detail'),
    path('modules/create/', views.module_create, name='module_create'),
    path('modules/<int:module_id>/update/', views.module_update, name='module_update'),
    path('modules/<int:module_id>/delete/', views.module_delete, name='module_delete'),
    
    # Feature Flag Management
    path('feature-flags/', views.feature_flag_list, name='feature_flag_list'),
    path('feature-flags/<int:flag_id>/', views.feature_flag_detail, name='feature_flag_detail'),
    
    # Subscription Package Management
    path('packages/', views.package_list, name='package_list'),
    path('packages/<int:package_id>/', views.package_detail, name='package_detail'),
    
    # Subscription Management
    path('subscriptions/', views.subscription_list, name='subscription_list'),
    path('subscriptions/<int:subscription_id>/', views.subscription_detail, name='subscription_detail'),
    
    # Organization Management
    path('organizations/', views.organization_list, name='organization_list'),
    path('organizations/<int:organization_id>/', views.organization_detail, name='organization_detail'),
    
    # Audit Log Management
    path('audit-logs/', views.audit_log_list, name='audit_log_list'),
]