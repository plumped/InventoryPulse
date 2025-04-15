from django.urls import path

from . import views

app_name = 'module_management'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('manage/', views.manage_modules, name='manage_modules'),
    path('subscribe/<int:module_id>/', views.subscribe_module, name='subscribe_module'),
    path('unsubscribe/<int:module_id>/', views.unsubscribe_module, name='unsubscribe_module'),
    path('renew/<int:subscription_id>/', views.renew_subscription, name='renew_subscription'),
    path('module/<str:module_code>/', views.module_details, name='module_details'),
    path('history/', views.subscription_history, name='subscription_history'),
    path('overview/', views.user_module_overview, name='user_module_overview'),
]
