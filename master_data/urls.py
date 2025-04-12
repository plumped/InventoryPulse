from django.urls import path

from master_data.views.currency_views import currency_list, currency_create, currency_update, currency_delete

urlpatterns = [
    path('', currency_list, name='currency_list'),
    path('create/', currency_create, name='currency_create'),
    path('<int:pk>/update/', currency_update, name='currency_update'),
    path('<int:pk>/delete/', currency_delete, name='currency_delete'),
]
