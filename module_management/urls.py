from django.urls import path

from . import views

urlpatterns = [
    # Module URLs
    path('modules/', views.module_list, name='module_list'),
    path('modules/<int:module_id>/', views.module_detail, name='module_detail'),
    path('modules/create/', views.module_create, name='module_create'),
    path('modules/<int:module_id>/update/', views.module_update, name='module_update'),
    path('modules/<int:module_id>/delete/', views.module_delete, name='module_delete'),

    # Feature Flag URLs
    path('feature-flags/', views.feature_flag_list, name='feature_flag_list'),
    path('feature-flags/<int:flag_id>/', views.feature_flag_detail, name='feature_flag_detail'),
    path('feature-flags/create/', views.feature_flag_create, name='feature_flag_create'),
    path('feature-flags/<int:flag_id>/update/', views.feature_flag_update, name='feature_flag_update'),
    path('feature-flags/<int:flag_id>/delete/', views.feature_flag_delete, name='feature_flag_delete'),

    # Subscription Package URLs
    path('packages/', views.package_list, name='package_list'),
    path('packages/<int:package_id>/', views.package_detail, name='package_detail'),
    path('packages/create/', views.package_create, name='package_create'),
    path('packages/<int:package_id>/update/', views.package_update, name='package_update'),
    path('packages/<int:package_id>/delete/', views.package_delete, name='package_delete'),

    # Subscription URLs
    path('subscriptions/', views.subscription_list, name='subscription_list'),
    path('subscriptions/<int:subscription_id>/', views.subscription_detail, name='subscription_detail'),
    path('subscriptions/create/', views.subscription_create, name='subscription_create'),
    path('subscriptions/<int:subscription_id>/update/', views.subscription_update, name='subscription_update'),
    path('subscriptions/<int:subscription_id>/delete/', views.subscription_delete, name='subscription_delete'),

    # API URLs for AJAX
    path('api/packages/<int:package_id>/', views.get_package_details, name='api_package_details'),
    path('api/modules/<str:module_code>/access/', views.check_module_access, name='api_check_module_access'),
    path('api/features/<str:feature_code>/access/', views.check_feature_access, name='api_check_feature_access'),

    # Dashboard (default view)
    path('', views.module_list, name='module_management_dashboard'),
]
