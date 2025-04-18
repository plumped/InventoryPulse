from django.shortcuts import redirect
from django.urls import path

from . import views


# Redirect to superadmin dashboard
def redirect_to_superadmin(request):
    if request.user.is_superuser:
        return redirect('superadmin:dashboard')
    return redirect('dashboard')

urlpatterns = [
    # API URLs for AJAX (these are still needed for the frontend)
    path('api/modules/<str:module_code>/access/', views.check_module_access, name='api_check_module_access'),
    path('api/features/<str:feature_code>/access/', views.check_feature_access, name='api_check_feature_access'),

    # Redirect all other URLs to superadmin dashboard
    path('', redirect_to_superadmin, name='module_management_dashboard'),
]
