from django.urls import path
from . import views

urlpatterns = [
    # Purchase Order Views
    path('', views.purchase_order_list, name='purchase_order_list'),
    path('create/', views.purchase_order_create, name='purchase_order_create'),
    path('create-from-template/<int:template_id>/', views.purchase_order_create_from_template,
         name='purchase_order_create_from_template'),
    path('create-from-recommendations/', views.purchase_order_create_from_recommendations,
         name='purchase_order_create_from_recommendations'),
    path('<int:pk>/', views.purchase_order_detail, name='purchase_order_detail'),
    path('<int:pk>/update/', views.purchase_order_update, name='purchase_order_update'),
    path('<int:pk>/delete/', views.purchase_order_delete, name='purchase_order_delete'),
    path('<int:pk>/print/', views.purchase_order_print, name='purchase_order_print'),
    path('<int:pk>/email/', views.purchase_order_email, name='purchase_order_email'),
    path('<int:pk>/mark-sent/', views.purchase_order_mark_sent, name='purchase_order_mark_sent'),
    path('<int:pk>/cancel/', views.purchase_order_cancel, name='purchase_order_cancel'),

    # Purchase Order Item Views
    path('<int:order_id>/items/add/', views.purchase_order_item_add, name='purchase_order_item_add'),
    path('<int:order_id>/items/<int:item_id>/update/', views.purchase_order_item_update,
         name='purchase_order_item_update'),
    path('<int:order_id>/items/<int:item_id>/delete/', views.purchase_order_item_delete,
         name='purchase_order_item_delete'),

    # Goods Receipt Views
    path('receipts/', views.goods_receipt_list, name='goods_receipt_list'),
    path('receipts/create/<int:order_id>/', views.goods_receipt_create, name='goods_receipt_create'),
    path('receipts/<int:pk>/', views.goods_receipt_detail, name='goods_receipt_detail'),
    path('receipts/<int:pk>/update/', views.goods_receipt_update, name='goods_receipt_update'),
    path('receipts/<int:pk>/complete/', views.goods_receipt_complete, name='goods_receipt_complete'),
    path('receipts/<int:pk>/cancel/', views.goods_receipt_cancel, name='goods_receipt_cancel'),

    # Template Views
    path('templates/', views.purchase_order_template_list, name='purchase_order_template_list'),
    path('templates/create/', views.purchase_order_template_create, name='purchase_order_template_create'),
    path('templates/<int:pk>/', views.purchase_order_template_detail, name='purchase_order_template_detail'),
    path('templates/<int:pk>/update/', views.purchase_order_template_update,
         name='purchase_order_template_update'),
    path('templates/<int:pk>/delete/', views.purchase_order_template_delete,
         name='purchase_order_template_delete'),

    # Recommendation Views
    path('recommendations/', views.purchase_recommendation_list, name='purchase_recommendation_list'),
    path('recommendations/generate/', views.generate_purchase_recommendations,
         name='generate_purchase_recommendations'),
    path('recommendations/<int:pk>/update-status/', views.update_recommendation_status,
         name='update_recommendation_status'),
]