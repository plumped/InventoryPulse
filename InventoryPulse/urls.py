from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core import views as core_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # === Admin ===
    path('admin/', admin.site.urls),

    # === Authentication ===
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='auth/password_change_form.html',
        success_url='/password_change/done/'
    ), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='auth/password_change_done.html'
    ), name='password_change_done'),

    # === Dashboard ===
    path('', core_views.dashboard, name='dashboard'),

    # === User Profile ===
    path('profile/', core_views.profile, name='profile'),

    path('rma/', include('rma.urls')),

    # === Products ===
    path('products/', include([
        path('', core_views.product_list, name='product_list'),
        path('low-stock/', core_views.low_stock_list, name='low_stock_list'),
        path('expiry-management/', core_views.expiry_management, name='expiry_management'),
        path('create/', core_views.product_create, name='product_create'),
        path('<int:pk>/', core_views.product_detail, name='product_detail'),
        path('<int:pk>/update/', core_views.product_update, name='product_update'),
        path('<int:pk>/photos/', core_views.product_photos, name='product_photos'),
        path('<int:pk>/photos/add/', core_views.product_photo_add, name='product_photo_add'),
        path('<int:pk>/photos/<int:photo_id>/delete/', core_views.product_photo_delete, name='product_photo_delete'),
        path('<int:pk>/photos/<int:photo_id>/set-primary/', core_views.product_photo_set_primary, name='product_photo_set_primary'),
        path('<int:pk>/attachments/', core_views.product_attachments, name='product_attachments'),
        path('<int:pk>/attachments/add/', core_views.product_attachment_add, name='product_attachment_add'),
        path('<int:pk>/attachments/<int:attachment_id>/delete/', core_views.product_attachment_delete, name='product_attachment_delete'),
        path('<int:pk>/attachments/<int:attachment_id>/download/', core_views.product_attachment_download, name='product_attachment_download'),
        path('<int:pk>/variants/', core_views.product_variants, name='product_variants'),
        path('<int:pk>/variants/add/', core_views.product_variant_add, name='product_variant_add'),
        path('<int:pk>/variants/<int:variant_id>/', core_views.product_variant_detail, name='product_variant_detail'),
        path('<int:pk>/variants/<int:variant_id>/update/', core_views.product_variant_update, name='product_variant_update'),
        path('<int:pk>/variants/<int:variant_id>/delete/', core_views.product_variant_delete, name='product_variant_delete'),
        path('<int:pk>/serials/', core_views.product_serials, name='product_serials'),
        path('<int:pk>/serials/add/', core_views.product_serial_add, name='product_serial_add'),
        path('<int:pk>/serials/bulk-add/', core_views.product_serial_bulk_add, name='product_serial_bulk_add'),
        path('<int:pk>/serials/<int:serial_id>/update/', core_views.product_serial_update, name='product_serial_update'),
        path('<int:pk>/serials/<int:serial_id>/delete/', core_views.product_serial_delete, name='product_serial_delete'),
        path('<int:pk>/batches/', core_views.product_batches, name='product_batches'),
        path('<int:pk>/batches/add/', core_views.product_batch_add, name='product_batch_add'),
        path('<int:pk>/batches/<int:batch_id>/update/', core_views.product_batch_update, name='product_batch_update'),
        path('<int:pk>/batches/<int:batch_id>/delete/', core_views.product_batch_delete, name='product_batch_delete'),
    ])),

    # === Currencies ===
    path('currencies/', include([
        path('', core_views.currency_list, name='currency_list'),
        path('create/', core_views.currency_create, name='currency_create'),
        path('<int:pk>/update/', core_views.currency_update, name='currency_update'),
        path('<int:pk>/delete/', core_views.currency_delete, name='currency_delete'),
    ])),

    # === Serial Numbers ===
    path('serialnumbers/', include([
        path('', core_views.serialnumber_list, name='serialnumber_list'),
        path('add/', core_views.serialnumber_add, name='serialnumber_add'),
        path('transfer/', core_views.serialnumber_transfer, name='serialnumber_transfer'),
        path('import/', core_views.serialnumber_import, name='serialnumber_import'),
        path('export/', core_views.serialnumber_export, name='serialnumber_export'),
        path('scan/', core_views.serialnumber_scan, name='serialnumber_scan'),
        path('search/', core_views.serialnumber_search, name='serialnumber_search'),
        path('batch-actions/', core_views.serialnumber_batch_actions, name='serialnumber_batch_actions'),
        path('<int:serial_id>/', core_views.serialnumber_detail, name='serialnumber_detail'),
        path('<int:serial_id>/history/', core_views.serialnumber_history, name='serialnumber_history'),
    ])),

    # === Batch Numbers ===
    path('batch-numbers/', include([
    path('', core_views.batch_number_list, name='batch_number_list'),
    path('<int:batch_id>/', core_views.batch_number_detail, name='batch_number_detail'),
    path('add/', core_views.batch_number_add, name='batch_number_add'),
    path('<int:batch_id>/edit/', core_views.batch_number_edit, name='batch_number_edit'),
    path('<int:batch_id>/delete/', core_views.batch_number_delete, name='batch_number_delete'),
    path('scan/', core_views.batch_number_scan, name='batch_number_scan'),
    path('transfer/', core_views.batch_number_transfer, name='batch_number_transfer'),
    path('import/', core_views.batch_number_import, name='batch_number_import'),
    path('export/', core_views.batch_number_export, name='batch_number_export'),
    ])),

    # === Variant Types ===
    path('variant-types/', include([
        path('', core_views.variant_type_list, name='variant_type_list'),
        path('add/', core_views.variant_type_add, name='variant_type_add'),
        path('<int:pk>/update/', core_views.variant_type_update, name='variant_type_update'),
        path('<int:pk>/delete/', core_views.variant_type_delete, name='variant_type_delete'),
    ])),

    # === Expiry Management ===
    path('expiry-management/', core_views.expiry_management, name='expiry_management'),

    # === Categories ===
    path('categories/', include([
        path('', core_views.category_list, name='category_list'),
        path('create/', core_views.category_create, name='category_create'),
        path('<int:pk>/update/', core_views.category_update, name='category_update'),
    ])),

    # === Import Management ===
    path('import/', include([
        path('', core_views.import_dashboard, name='import_dashboard'),
        path('products/', core_views.import_products, name='import_products'),
        path('suppliers/', core_views.import_suppliers, name='import_suppliers'),
        path('categories/', core_views.import_categories, name='import_categories'),
        path('supplier-products/', core_views.import_supplier_products, name='import_supplier_products'),
        path('serialnumbers/', core_views.import_serialnumbers, name='import_serialnumbers'),
        path('warehouses/', core_views.import_warehouses, name='import_warehouses'),
        path('departments/', core_views.import_departments, name='import_departments'),
        path('warehouse-products/', core_views.import_warehouse_products, name='import_warehouse_products'),
        path('logs/', core_views.import_log_list, name='import_log_list'),
        path('logs/<int:pk>/', core_views.import_log_detail, name='import_log_detail'),
        path('logs/<int:log_id>/delete/', core_views.delete_import_log, name='delete_import_log'),
        path('logs/bulk-delete/', core_views.bulk_delete_import_logs, name='bulk_delete_import_logs'),
        path('logs/export/', core_views.export_import_logs, name='export_import_logs'),
        path('logs/<int:log_id>/download-errors/', core_views.download_error_file, name='download_error_file'),
    ])),

    # === External Apps ===
    path('inventory/', include('inventory.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('order/', include('order.urls')),
    path('admin-dashboard/', include('admin_dashboard.urls')),
    path('access/', include('accessmanagement.urls')),
    path('interfaces/', include('interfaces.urls')),
    path('documents/', include('documents.urls')),  # New documents app URLs

    # === API Endpoints ===
    path('api/v1/', include('api.urls')),
    path('api/products/search/', core_views.products_search, name='api_products_search'),

    # === Select2 ===
    path('select2/', include('django_select2.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
