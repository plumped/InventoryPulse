from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import UserProfile
from .signals import check_password_history, add_password_to_history


class HistoryCheckingPasswordChangeForm(PasswordChangeForm):
    """
    Custom password change form that checks password history.
    """

    def clean_new_password1(self):
        """
        Validate that the new password hasn't been used before.
        """
        password = super().clean_new_password1()

        # Check if the password is in the history
        if check_password_history(self.user, password):
            raise ValidationError(
                "You cannot reuse a previous password. Please choose a different password.",
                code='password_in_history'
            )

        return password

    def save(self, commit=True):
        """
        Save the new password and add it to the history.
        """
        user = super().save(commit=commit)

        # Add the new password to history
        add_password_to_history(user)

        return user


class HistoryCheckingSetPasswordForm(SetPasswordForm):
    """
    Custom set password form that checks password history.
    Used for password reset.
    """

    def clean_new_password1(self):
        """
        Validate that the new password hasn't been used before.
        """
        password = super().clean_new_password1()

        # Check if the password is in the history
        if check_password_history(self.user, password):
            raise ValidationError(
                "You cannot reuse a previous password. Please choose a different password.",
                code='password_in_history'
            )

        return password

    def save(self, commit=True):
        """
        Save the new password and add it to the history.
        """
        user = super().save(commit=commit)

        # Add the new password to history
        add_password_to_history(user)

        return user


class RegistrationForm(UserCreationForm):
    """
    Custom registration form that extends UserCreationForm.
    Includes additional fields for email, company information, and subdomain.
    """
    email = forms.EmailField(required=True, help_text="Required. Enter a valid email address.")
    company_name = forms.CharField(max_length=100, required=True, help_text="Required. Enter your company name.")
    subdomain = forms.CharField(
        max_length=50,
        required=True,
        help_text="Required. This will be your unique subdomain (e.g., 'yourcompany' for yourcompany.inventorypulse.com)."
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'company_name', 'subdomain')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email

    def clean_subdomain(self):
        subdomain = self.cleaned_data.get('subdomain')

        # Convert to lowercase and remove spaces
        subdomain = subdomain.lower().strip().replace(' ', '')

        # Check if subdomain contains only alphanumeric characters and hyphens
        import re
        if not re.match(r'^[a-z0-9-]+$', subdomain):
            raise ValidationError("Subdomain can only contain lowercase letters, numbers, and hyphens.")

        # Check if subdomain starts or ends with hyphen
        if subdomain.startswith('-') or subdomain.endswith('-'):
            raise ValidationError("Subdomain cannot start or end with a hyphen.")

        # Check if subdomain is already in use
        from master_data.models.organisations_models import Organization
        if Organization.objects.filter(subdomain=subdomain).exists():
            raise ValidationError("This subdomain is already in use. Please choose a different one.")

        # Check if subdomain is a reserved word
        reserved_words = ['www', 'admin', 'api', 'app', 'dashboard', 'login', 'register', 'static', 'media']
        if subdomain in reserved_words:
            raise ValidationError(f"'{subdomain}' is a reserved word and cannot be used as a subdomain.")

        return subdomain

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']

        if commit:
            user.save()
            # Create user profile with company information
            from master_data.models.organisations_models import Organization
            from module_management.models import SubscriptionPackage, Subscription
            import uuid
            import datetime

            # Generate a unique code for the organization
            org_code = f"ORG-{uuid.uuid4().hex[:8].upper()}"

            # Get the subdomain from cleaned data
            subdomain = self.cleaned_data['subdomain']

            # Create the organization with subdomain
            company = Organization.objects.create(
                name=self.cleaned_data['company_name'],
                code=org_code,
                subdomain=subdomain,
                subscription_active=True
            )

            # Add the user as an admin of the organization
            company.admin_users.add(user)

            # Create user profile if it doesn't exist
            if not UserProfile.objects.filter(user=user).exists():
                UserProfile.objects.create(
                    user=user,
                    organization=company
                )

            # Assign the Basic subscription package to the organization
            basic_package = None
            try:
                basic_package = SubscriptionPackage.objects.get(code='basic')
            except SubscriptionPackage.DoesNotExist:
                # Create a basic package if it doesn't exist
                import logging
                logger = logging.getLogger('accessmanagement')
                logger.warning(
                    f"Basic subscription package not found during registration for {company.name}. Creating default package.")

                try:
                    # Create a default Basic package
                    from decimal import Decimal
                    basic_package = SubscriptionPackage.objects.create(
                        name='Basic',
                        code='basic',
                        description='Basic inventory management for small businesses',
                        price_monthly=Decimal('49.99'),
                        price_yearly=Decimal('499.90'),
                        is_active=True
                    )

                    # Try to add the inventory module if it exists
                    try:
                        from module_management.models import Module
                        inventory_module = Module.objects.filter(code='inventory', is_active=True).first()
                        if inventory_module:
                            basic_package.modules.add(inventory_module)
                    except Exception as e:
                        logger.warning(f"Could not add inventory module to basic package: {str(e)}")
                except Exception as e:
                    # If we can't create the package, log the error
                    logger.error(f"Error creating basic subscription package: {str(e)}")
                    # Create a minimal package to avoid NoneType errors
                    try:
                        basic_package = SubscriptionPackage.objects.create(
                            name='Basic',
                            code='basic-' + str(uuid.uuid4())[:8],  # Ensure unique code
                            description='Basic package',
                            price_monthly=Decimal('0.00'),
                            price_yearly=Decimal('0.00'),
                            is_active=True
                        )
                    except Exception as e2:
                        logger.error(f"Critical error creating fallback package: {str(e2)}")
                        # If we still can't create a package, log it but continue
                        # The template has null checks to handle this case

            # Set the subscription package on the organization
            company.subscription_package = basic_package
            company.save()

            # Create a subscription record
            today = datetime.date.today()
            # Default to a 30-day trial period
            end_date = today + datetime.timedelta(days=30)

            # Only create a subscription if we have a package
            if basic_package:
                try:
                    Subscription.objects.create(
                        organization=company,
                        package=basic_package,
                        subscription_type='trial',
                        start_date=today,
                        end_date=end_date,
                        is_active=True,
                        payment_status='pending'
                    )
                except Exception as e:
                    # Log the error but continue
                    import logging
                    logger = logging.getLogger('accessmanagement')
                    logger.error(f"Error creating subscription: {str(e)}")
                    # The user can still access the system without a subscription record
                    # They'll need to set up a subscription later

            # Add the new password to history
            add_password_to_history(user)

        return user
