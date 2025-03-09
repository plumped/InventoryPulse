from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core import views as core_views

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='auth/password_change_form.html',
        success_url='/password_change/done/'
    ), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='auth/password_change_done.html'
    ), name='password_change_done'),

    # Dashboard
    path('', core_views.dashboard, name='dashboard'),

    # Core app
    path('products/', include([
        path('', core_views.product_list, name='product_list'),
        path('low-stock/', core_views.low_stock_list, name='low_stock_list'),
        path('create/', core_views.product_create, name='product_create'),
        path('<int:pk>/', core_views.product_detail, name='product_detail'),
        path('<int:pk>/update/', core_views.product_update, name='product_update'),
    ])),

    path('categories/', include([
        path('', core_views.category_list, name='category_list'),
        path('create/', core_views.category_create, name='category_create'),
        path('<int:pk>/update/', core_views.category_update, name='category_update'),
    ])),

    # Include other app URLs
    path('inventory/', include('inventory.urls')),
    path('suppliers/', include('suppliers.urls')),

    # User profile
    path('profile/', core_views.profile, name='profile'),

    path('import/', include([
        path('', core_views.import_dashboard, name='import_dashboard'),
        path('products/', core_views.import_products, name='import_products'),
        path('suppliers/', core_views.import_suppliers, name='import_suppliers'),
        path('categories/', core_views.import_categories, name='import_categories'),
        path('supplier-products/', core_views.import_supplier_products, name='import_supplier_products'),

        # Neue Import-URLs für Lager-/Abteilungsverwaltung
        path('warehouses/', core_views.import_warehouses, name='import_warehouses'),
        path('departments/', core_views.import_departments, name='import_departments'),
        path('warehouse-products/', core_views.import_warehouse_products, name='import_warehouse_products'),

        # Bereits vorhandene Log-URLs
        path('logs/', core_views.import_log_list, name='import_log_list'),
        path('logs/<int:pk>/', core_views.import_log_detail, name='import_log_detail'),

        # Neue Log-URLs
        path('logs/<int:log_id>/delete/', core_views.delete_import_log, name='delete_import_log'),
        path('logs/bulk-delete/', core_views.bulk_delete_import_logs, name='bulk_delete_import_logs'),
        path('logs/export/', core_views.export_import_logs, name='export_import_logs'),
        path('logs/<int:log_id>/download-errors/', core_views.download_error_file, name='download_error_file'),
    ])),

    path('permissions/', include([
        path('', core_views.permission_management, name='permission_management'),
        path('user/', core_views.get_user_permissions, name='get_user_permissions'),
    ])),
]