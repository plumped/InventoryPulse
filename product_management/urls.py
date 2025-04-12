from django.urls import path, include

from product_management.views import product_views, variant_views, category_views
from product_management.views.product_media_views import (
    product_photos, product_photo_add, product_photo_delete, product_photo_set_primary,
    product_attachments, product_attachment_add, product_attachment_delete, product_attachment_download
)
from product_management.views.product_views import low_stock_list
from product_management.views.variant_views import (
    product_variants, product_variant_add, product_variant_detail,
    product_variant_update, product_variant_delete
)

urlpatterns = [
    # Hauptproduktrouten
    path('products/', include([
        path('', product_views.product_list, name='product_list'),
        path('create/', product_views.product_create, name='product_create'),
        path('<int:pk>/', product_views.product_detail, name='product_detail'),
        path('<int:pk>/update/', product_views.product_update, name='product_update'),

        # Produktmedienverwaltung (Fotos)
        path('<int:pk>/photos/', include([
            path('', product_photos, name='product_photos'),
            path('add/', product_photo_add, name='product_photo_add'),
            path('<int:photo_id>/delete/', product_photo_delete, name='product_photo_delete'),
            path('<int:photo_id>/set-primary/', product_photo_set_primary, name='product_photo_set_primary'),
        ])),

        # Produktanlagenmanagement (Dokumente)
        path('<int:pk>/attachments/', include([
            path('', product_attachments, name='product_attachments'),
            path('add/', product_attachment_add, name='product_attachment_add'),
            path('<int:attachment_id>/delete/', product_attachment_delete, name='product_attachment_delete'),
            path('<int:attachment_id>/download/', product_attachment_download, name='product_attachment_download'),
        ])),

        # Produktvariantenverwaltung
        path('<int:pk>/variants/', include([
            path('', product_variants, name='product_variants'),
            path('add/', product_variant_add, name='product_variant_add'),
            path('<int:variant_id>/', product_variant_detail, name='product_variant_detail'),
            path('<int:variant_id>/update/', product_variant_update, name='product_variant_update'),
            path('<int:variant_id>/delete/', product_variant_delete, name='product_variant_delete'),
        ])),
    ])),

    # Lagerbestand
    path('low-stock/', low_stock_list, name='low_stock_list'),

    # Variantentypen
    path('variant-types/', include([
        path('', variant_views.variant_type_list, name='variant_type_list'),  # geändert von core_views zu variant_views
        path('add/', variant_views.variant_type_add, name='variant_type_add'),
        path('<int:pk>/update/', variant_views.variant_type_update, name='variant_type_update'),
        path('<int:pk>/delete/', variant_views.variant_type_delete, name='variant_type_delete'),
    ])),

    # Kategorien
    path('categories/', include([
        path('', category_views.category_list, name='category_list'),  # geändert von core_views zu category_views
        path('create/', category_views.category_create, name='category_create'),
        path('<int:pk>/update/', category_views.category_update, name='category_update'),
    ])),
]
