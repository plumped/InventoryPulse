from django import forms

from master_data.models.systemsettings_models import WorkflowSettings


class WorkflowSettingsForm(forms.ModelForm):
    """Form for workflow settings."""

    class Meta:
        model = WorkflowSettings
        fields = '__all__'
        widgets = {
            'order_approval_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order_approval_threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'skip_draft_for_small_orders': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'small_order_threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'auto_approve_preferred_suppliers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'send_order_emails': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_separate_approver': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
