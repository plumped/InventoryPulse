from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from two_factor.urls import urlpatterns as tf_urls

from accessmanagement import views as access_views
from accessmanagement.forms import HistoryCheckingPasswordChangeForm, HistoryCheckingSetPasswordForm
from core import views as core_views

urlpatterns = [
    # === Landing Page (für nicht eingeloggte Benutzer) ===
    path('', core_views.landing_page, name='landing_page'),

    # === Admin ===
    path('admin/', admin.site.urls),

    # === Authentication ===
    # Standard login (fallback)
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),

    # Registration
    path('register/', access_views.register, name='register'),

    # Logout view
    path('logout/', auth_views.LogoutView.as_view(next_page='landing_page'), name='logout'),

    # Two-factor authentication
    path('', include(tf_urls)),

    # Custom password change with history checking
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='auth/password_change_form.html',
        success_url='/password_change/done/',
        form_class=HistoryCheckingPasswordChangeForm
    ), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='auth/password_change_done.html'
    ), name='password_change_done'),

    # Password reset functionality
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='auth/password_reset_form.html',
        email_template_name='auth/password_reset_email.html',
        subject_template_name='auth/password_reset_subject.txt',
        success_url='/password_reset/done/'
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='auth/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='auth/password_reset_confirm.html',
        success_url='/reset/done/',
        form_class=HistoryCheckingSetPasswordForm
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='auth/password_reset_complete.html'
    ), name='password_reset_complete'),

    # === Dashboard ===
    path('dashboard/', include('analytics.urls')),

    # === User Profile ===
    path('profile/', core_views.profile, name='profile'),

    # === Main Application Modules ===
    path('products/', include('product_management.urls')),
    path('tracking/', include('tracking.urls')),
    path('data/', include('data_operations.urls')),
    path('master-data/', include('master_data.urls')),
    path('rma/', include('rma.urls')),
    path('inventory/', include('inventory.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('orders/', include('order.urls')),
    path('admin/', include('admin_dashboard.urls')),
    path('access/', include('accessmanagement.urls')),
    path('interfaces/', include('interfaces.urls')),
    path('documents/', include('documents.urls')),
    path('modules/', include('module_management.urls')),

    # === API Endpoints ===
    path('api/v1/', include('api.urls')),

    path('api/products/search/', core_views.products_search, name='api_products_search'),
    path('api/product-variants/', core_views.api_product_variants, name='api_product_variants'),

    path('docs/', core_views.documentation_view, name='docs'),
    path('docs/<path:path>', core_views.documentation_view, name='docs_with_path'),

    # === Superadmin Dashboard ===
    path('superadmin/', include('superadmin.urls')),

    # === Select2 ===
    path('select2/', include('django_select2.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
