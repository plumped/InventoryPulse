from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from master_data.models.organisations_models import Organization
from module_management.models import SubscriptionPackage


class OrganizationRegistrationForm(forms.ModelForm):
    """
    Form for registering a new organization (tenant) and its admin user.
    """
    # Organization fields
    name = forms.CharField(max_length=200, required=True, label="Organization Name")
    subdomain = forms.CharField(max_length=100, required=True, label="Subdomain",
                                help_text="This will be used as your subdomain (e.g., 'acme' for acme.example.com)")

    # Admin user fields
    admin_email = forms.EmailField(required=True, label="Admin Email")
    admin_first_name = forms.CharField(max_length=30, required=True, label="Admin First Name")
    admin_last_name = forms.CharField(max_length=30, required=True, label="Admin Last Name")
    admin_password = forms.CharField(widget=forms.PasswordInput, required=True, label="Admin Password")
    admin_password_confirm = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm Admin Password")

    # Subscription fields
    subscription_package = forms.ModelChoiceField(
        queryset=SubscriptionPackage.objects.filter(is_active=True),
        required=True,
        label="Subscription Package"
    )

    class Meta:
        model = Organization
        fields = ['name', 'subdomain', 'email', 'phone', 'address', 'website']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Check if active subscription packages exist
        active_packages = SubscriptionPackage.objects.filter(is_active=True)
        if not active_packages.exists():
            # Log this issue
            import logging
            logger = logging.getLogger(__name__)
            logger.error("No active subscription packages found for registration")

            # You could set a default error message on the field
            self.fields[
                'subscription_package'].help_text = "No active subscription packages available. Please contact the administrator."

        self.fields['subscription_package'].queryset = active_packages

    def clean_subdomain(self):
        """
        Validate that the subdomain is unique and contains only valid characters.
        """
        subdomain = self.cleaned_data.get('subdomain')

        # Convert to lowercase and slugify
        subdomain = slugify(subdomain.lower())

        # Check if subdomain already exists
        if Organization.objects.filter(subdomain=subdomain).exists():
            raise forms.ValidationError("This subdomain is already in use. Please choose another one.")

        return subdomain

    def clean_admin_email(self):
        """
        Validate that the admin email is unique.
        """
        email = self.cleaned_data.get('admin_email')

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use. Please choose another one.")

        return email

    def clean(self):
        """
        Validate that the passwords match.
        """
        cleaned_data = super().clean()
        password = cleaned_data.get('admin_password')
        password_confirm = cleaned_data.get('admin_password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('admin_password_confirm', "The passwords do not match.")

        # Validate password strength
        if password:
            try:
                validate_password(password)
            except forms.ValidationError as error:
                self.add_error('admin_password', error)

        return cleaned_data

    def save(self, commit=True):
        """
        Save the organization and create the admin user.
        """
        # Save the organization
        organization = super().save(commit=False)

        # Get subscription package safely
        subscription_package = self.cleaned_data.get('subscription_package')
        if subscription_package:
            organization.subscription_package = subscription_package
        else:
            # Log the issue
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Creating organization without subscription package")
            # You might want to set a default package or handle this case differently

        organization.subscription_active = True

        if commit:
            organization.save()

            # Create the admin user
            admin_user = User.objects.create_user(
                username=self.cleaned_data.get('admin_email'),
                email=self.cleaned_data.get('admin_email'),
                password=self.cleaned_data.get('admin_password'),
                first_name=self.cleaned_data.get('admin_first_name'),
                last_name=self.cleaned_data.get('admin_last_name'),
                is_staff=True  # Allow access to admin site
            )

            # Add the user to the organization's admin_users
            organization.admin_users.add(admin_user)

            # Assign the Administrator role to the user
            from accessmanagement.models import Role, UserRole
            try:
                admin_role = Role.objects.get(name='Administrator')
                UserRole.objects.create(
                    user=admin_user,
                    role=admin_role,
                    organization=organization
                )
                logger.info(f"Administrator role assigned to user {admin_user.username} for organization {organization.name}")
            except Role.DoesNotExist:
                logger.error(f"Administrator role not found when registering user {admin_user.username}")
                # Here you could implement a fallback or issue a warning

            # Create a user profile for the admin user
            from accessmanagement.models import UserProfile
            UserProfile.objects.create(
                user=admin_user,
                organization=organization
            )

        return organization
