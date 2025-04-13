from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

from core import views as core_views

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

    path('', include('product_management.urls')),
    path('', include('tracking.urls')),
    path('', include('data_operations.urls')),
    path('', include('analytics.urls')),
    path('', include('master_data.urls')),


    # === User Profile ===
    path('profile/', core_views.profile, name='profile'),

    path('rma/', include('rma.urls')),

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
    path('api/product-variants/', core_views.api_product_variants, name='api_product_variants'),

    path('docs/', core_views.documentation_view, name='docs'),
    path('docs/<path:path>', core_views.documentation_view, name='docs_with_path'),

    # === Select2 ===
    path('select2/', include('django_select2.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
