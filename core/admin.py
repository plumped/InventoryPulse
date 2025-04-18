from django.contrib import admin
from django.utils.html import format_html

from .models import SensitiveData, AuditLog


@admin.register(SensitiveData)
class SensitiveDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'masked_credit_card', 'masked_tax_id', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

    def masked_credit_card(self, obj):
        if obj.credit_card_number:
            # Show only last 4 digits
            return f"****-****-****-{obj.credit_card_number[-4:]}" if len(obj.credit_card_number) >= 4 else "****"
        return "Not set"

    masked_credit_card.short_description = "Credit Card"

    def masked_tax_id(self, obj):
        if obj.tax_id:
            # Show only last 4 characters
            return f"****{obj.tax_id[-4:]}" if len(obj.tax_id) >= 4 else "****"
        return "Not set"

    masked_tax_id.short_description = "Tax ID"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'content_type', 'object_id', 'ip_address')
    list_filter = ('action', 'timestamp', 'content_type')
    search_fields = ('user__username', 'ip_address', 'user_agent', 'object_id')
    readonly_fields = ('user', 'action', 'timestamp', 'ip_address', 'user_agent',
                       'content_type', 'object_id', 'data', 'before_state', 'after_state',
                       'content_object_link')
    fieldsets = (
        (None, {
            'fields': ('user', 'action', 'timestamp', 'ip_address', 'user_agent')
        }),
        ('Object Information', {
            'fields': ('content_type', 'object_id', 'content_object_link')
        }),
        ('Change Data', {
            'fields': ('data', 'before_state', 'after_state'),
            'classes': ('collapse',)
        }),
    )

    def content_object_link(self, obj):
        if obj.content_type and obj.object_id:
            try:
                model_class = obj.content_type.model_class()
                if model_class:
                    model_obj = model_class.objects.filter(pk=obj.object_id).first()
                    if model_obj:
                        admin_url = f"/admin/{obj.content_type.app_label}/{obj.content_type.model}/{obj.object_id}/change/"
                        return format_html('<a href="{}">{}</a>', admin_url, str(model_obj))
            except Exception:
                pass
        return "N/A"

    content_object_link.short_description = "Object Link"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete audit logs
        return request.user.is_superuser
