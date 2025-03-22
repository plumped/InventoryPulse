from django.urls import path
from . import views

urlpatterns = [
    # Document management
    path('', views.document_list, name='document_list'),
    path('upload/', views.document_upload, name='document_upload'),
    path('<int:pk>/', views.document_detail, name='document_detail'),
    path('<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('<int:pk>/process/', views.document_process, name='document_process'),
    path('<int:pk>/match/', views.document_match, name='document_match'),

    # Document templates
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/', views.template_detail, name='template_detail'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('<int:pk>/match-to-template/<int:template_id>/', views.match_document_to_template,
         name='match_document_to_template'),

    # Template fields
    path('templates/<int:template_id>/fields/add/', views.field_create, name='field_create'),
    path('templates/<int:template_id>/fields/<int:pk>/edit/', views.field_edit, name='field_edit'),
    path('templates/<int:template_id>/fields/<int:pk>/delete/', views.field_delete, name='field_delete'),

    # Visual editor for fields
    path('templates/<int:template_id>/editor/', views.field_mapping_editor, name='field_mapping_editor'),

    # AJAX endpoints
    path('ajax/get-document-image/<int:pk>/', views.get_document_image, name='get_document_image'),
    path('ajax/get-document-ocr-data/<int:pk>/', views.get_document_ocr_data, name='get_document_ocr_data'),
    path('ajax/save-field-coordinates/', views.save_field_coordinates, name='save_field_coordinates'),
    path('ajax/extract-field-value/', views.extract_field_value, name='extract_field_value'),
    path('ajax/match-document-to-order/<int:pk>/', views.match_document_to_order, name='match_document_to_order'),

    path('ajax/field-suggestions/', views.get_field_suggestions, name='get_field_suggestions'),
    path('ajax/get-standard-fields/', views.get_standard_fields, name='get_standard_fields'),

]