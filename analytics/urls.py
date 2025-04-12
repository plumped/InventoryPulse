from django.urls import path

from analytics.views.dashboard_views import dashboard

# URL-Muster für die Analytics-App
urlpatterns = [
    # === Dashboard ===
    path('', dashboard, name='dashboard'),
]
