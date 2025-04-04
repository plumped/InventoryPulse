from django.urls import path
from . import views

urlpatterns = [
    # List and create RMAs
    path('', views.rma_list, name='rma_list'),
    path('create/', views.rma_create, name='rma_create'),

    # RMA CRUD operations
    path('<int:pk>/', views.rma_detail, name='rma_detail'),
    path('<int:pk>/update/', views.rma_update, name='rma_update'),
    path('<int:pk>/delete/', views.rma_delete, name='rma_delete'),

    # RMA items
    path('<int:pk>/add-item/', views.rma_add_item, name='rma_add_item'),
    path('<int:pk>/add-item/<int:receipt_item_id>/', views.rma_add_item, name='rma_add_item_from_receipt'),
    path('<int:pk>/edit-item/<int:item_id>/', views.rma_edit_item, name='rma_edit_item'),
    path('<int:pk>/delete-item/<int:item_id>/', views.rma_delete_item, name='rma_delete_item'),
    path('<int:pk>/toggle-item-resolved/<int:item_id>/', views.rma_toggle_item_resolved,
         name='rma_toggle_item_resolved'),

    # Photos
    path('<int:pk>/add-photos/<int:item_id>/', views.rma_add_photos, name='rma_add_photos'),
    path('<int:pk>/delete-photo/<int:item_id>/<int:photo_id>/', views.rma_delete_photo, name='rma_delete_photo'),

    # Documents
    path('<int:pk>/add-document/', views.rma_add_document, name='rma_add_document'),
    path('<int:pk>/delete-document/<int:document_id>/', views.rma_delete_document, name='rma_delete_document'),

    # Comments
    path('<int:pk>/delete-comment/<int:comment_id>/', views.rma_delete_comment, name='rma_delete_comment'),
    path('<int:pk>/comments/', views.rma_comments, name='rma_comments'),

    # History
    path('<int:pk>/history/', views.rma_history, name='rma_history'),

    # Print
    path('<int:pk>/print/', views.rma_print, name='rma_print'),

    # AJAX endpoints
    path('get-receipt-item-details/', views.get_receipt_item_details, name='get_receipt_item_details'),
    path('order/<int:order_id>/receipt/<int:receipt_id>/create-rma/',
         views.rma_create_from_receipt,
         name='rma_create_from_receipt'),
]