from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404

from core.models import AuditLog
from master_data.models.organisations_models import Organization
from module_management.models import Module, FeatureFlag, SubscriptionPackage, Subscription


def is_superuser(user):
    """Check if user is a superuser"""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def dashboard(request):
    """Superadmin dashboard view"""
    # Get counts for dashboard widgets
    module_count = Module.objects.count()
    active_module_count = Module.objects.filter(is_active=True).count()
    
    package_count = SubscriptionPackage.objects.count()
    active_package_count = SubscriptionPackage.objects.filter(is_active=True).count()
    
    subscription_count = Subscription.objects.count()
    active_subscription_count = Subscription.objects.filter(is_active=True).count()
    
    organization_count = Organization.objects.count()
    
    # Get recent audit logs for the activity feed
    recent_logs = AuditLog.objects.all().order_by('-timestamp')[:10]
    
    context = {
        'module_count': module_count,
        'active_module_count': active_module_count,
        'package_count': package_count,
        'active_package_count': active_package_count,
        'subscription_count': subscription_count,
        'active_subscription_count': active_subscription_count,
        'organization_count': organization_count,
        'recent_logs': recent_logs,
    }
    
    return render(request, 'superadmin/dashboard.html', context)


# Module Management Views
@login_required
@user_passes_test(is_superuser)
def module_list(request):
    """View to list all modules"""
    modules = Module.objects.all()

    # Count feature flags for each module
    modules = modules.annotate(feature_count=Count('feature_flags'))

    # Count packages that include each module
    modules = modules.annotate(package_count=Count('subscription_packages'))

    context = {
        'modules': modules,
        'active_modules': modules.filter(is_active=True).count(),
        'total_modules': modules.count(),
    }
    return render(request, 'superadmin/module_list.html', context)


@login_required
@user_passes_test(is_superuser)
def module_detail(request, module_id):
    """View to show details of a specific module"""
    module = get_object_or_404(Module, id=module_id)

    # Get feature flags for this module
    feature_flags = module.feature_flags.all()

    # Get packages that include this module
    packages = module.subscription_packages.all()

    context = {
        'module': module,
        'feature_flags': feature_flags,
        'packages': packages,
    }
    return render(request, 'superadmin/module_detail.html', context)


@login_required
@user_passes_test(is_superuser)
def module_create(request):
    """View to create a new module"""
    if request.method == 'POST':
        # Process form data
        name = request.POST.get('name')
        code = request.POST.get('code')
        description = request.POST.get('description')
        price_monthly = request.POST.get('price_monthly')
        price_yearly = request.POST.get('price_yearly')
        is_active = request.POST.get('is_active') == 'on'

        # Create module
        module = Module.objects.create(
            name=name,
            code=code,
            description=description,
            price_monthly=price_monthly,
            price_yearly=price_yearly,
            is_active=is_active
        )

        # Log the action
        content_type = ContentType.objects.get_for_model(Module)
        AuditLog.objects.create(
            user=request.user,
            action='create',
            content_type=content_type,
            object_id=module.id,
            data={'name': name, 'code': code}
        )

        messages.success(request, f'Module "{module.name}" created successfully.')
        return redirect('superadmin:module_detail', module_id=module.id)

    return render(request, 'superadmin/module_form.html', {'action': 'Create'})


@login_required
@user_passes_test(is_superuser)
def module_update(request, module_id):
    """View to update an existing module"""
    module = get_object_or_404(Module, id=module_id)

    if request.method == 'POST':
        # Store the before state for audit log
        before_state = {
            'name': module.name,
            'code': module.code,
            'description': module.description,
            'price_monthly': str(module.price_monthly),
            'price_yearly': str(module.price_yearly),
            'is_active': module.is_active
        }

        # Process form data
        module.name = request.POST.get('name')
        module.code = request.POST.get('code')
        module.description = request.POST.get('description')
        module.price_monthly = request.POST.get('price_monthly')
        module.price_yearly = request.POST.get('price_yearly')
        module.is_active = request.POST.get('is_active') == 'on'

        # Save module
        module.save()

        # Log the action
        after_state = {
            'name': module.name,
            'code': module.code,
            'description': module.description,
            'price_monthly': str(module.price_monthly),
            'price_yearly': str(module.price_yearly),
            'is_active': module.is_active
        }
        
        content_type = ContentType.objects.get_for_model(Module)
        AuditLog.objects.create(
            user=request.user,
            action='update',
            content_type=content_type,
            object_id=module.id,
            before_state=before_state,
            after_state=after_state
        )

        messages.success(request, f'Module "{module.name}" updated successfully.')
        return redirect('superadmin:module_detail', module_id=module.id)

    context = {
        'module': module,
        'action': 'Update'
    }
    return render(request, 'superadmin/module_form.html', context)


@login_required
@user_passes_test(is_superuser)
def module_delete(request, module_id):
    """View to delete a module"""
    module = get_object_or_404(Module, id=module_id)

    if request.method == 'POST':
        module_name = module.name
        module_id = module.id
        
        # Store data for audit log
        before_state = {
            'name': module.name,
            'code': module.code,
            'description': module.description,
            'price_monthly': str(module.price_monthly),
            'price_yearly': str(module.price_yearly),
            'is_active': module.is_active
        }
        
        # Delete the module
        module.delete()
        
        # Log the action
        content_type = ContentType.objects.get_for_model(Module)
        AuditLog.objects.create(
            user=request.user,
            action='delete',
            content_type=content_type,
            object_id=module_id,
            before_state=before_state
        )
        
        messages.success(request, f'Module "{module_name}" deleted successfully.')
        return redirect('superadmin:module_list')

    context = {
        'module': module,
        'action': 'Delete'
    }
    return render(request, 'superadmin/module_confirm_delete.html', context)


# Feature Flag Management Views
@login_required
@user_passes_test(is_superuser)
def feature_flag_list(request):
    """View to list all feature flags"""
    feature_flags = FeatureFlag.objects.all()
    
    context = {
        'feature_flags': feature_flags,
        'active_flags': feature_flags.filter(is_active=True).count(),
        'total_flags': feature_flags.count(),
    }
    return render(request, 'superadmin/feature_flag_list.html', context)


@login_required
@user_passes_test(is_superuser)
def feature_flag_detail(request, flag_id):
    """View to show details of a specific feature flag"""
    feature_flag = get_object_or_404(FeatureFlag, id=flag_id)
    
    # Get packages that include this feature flag
    packages = feature_flag.subscription_packages.all()
    
    context = {
        'feature_flag': feature_flag,
        'packages': packages,
    }
    return render(request, 'superadmin/feature_flag_detail.html', context)


# Subscription Package Management Views
@login_required
@user_passes_test(is_superuser)
def package_list(request):
    """View to list all subscription packages"""
    packages = SubscriptionPackage.objects.all()
    
    context = {
        'packages': packages,
        'active_packages': packages.filter(is_active=True).count(),
        'total_packages': packages.count(),
    }
    return render(request, 'superadmin/package_list.html', context)


@login_required
@user_passes_test(is_superuser)
def package_detail(request, package_id):
    """View to show details of a specific subscription package"""
    package = get_object_or_404(SubscriptionPackage, id=package_id)
    
    # Get modules in this package
    modules = package.modules.all()
    
    # Get feature flags in this package
    feature_flags = package.feature_flags.all()
    
    # Get subscriptions for this package
    subscriptions = package.subscriptions.all()
    
    context = {
        'package': package,
        'modules': modules,
        'feature_flags': feature_flags,
        'subscriptions': subscriptions,
    }
    return render(request, 'superadmin/package_detail.html', context)


# Subscription Management Views
@login_required
@user_passes_test(is_superuser)
def subscription_list(request):
    """View to list all subscriptions"""
    subscriptions = Subscription.objects.all()
    
    context = {
        'subscriptions': subscriptions,
        'active_subscriptions': subscriptions.filter(is_active=True).count(),
        'total_subscriptions': subscriptions.count(),
    }
    return render(request, 'superadmin/subscription_list.html', context)


@login_required
@user_passes_test(is_superuser)
def subscription_detail(request, subscription_id):
    """View to show details of a specific subscription"""
    subscription = get_object_or_404(Subscription, id=subscription_id)
    
    context = {
        'subscription': subscription,
    }
    return render(request, 'superadmin/subscription_detail.html', context)


# Organization Management Views
@login_required
@user_passes_test(is_superuser)
def organization_list(request):
    """View to list all organizations"""
    organizations = Organization.objects.all()
    
    context = {
        'organizations': organizations,
        'total_organizations': organizations.count(),
    }
    return render(request, 'superadmin/organization_list.html', context)


@login_required
@user_passes_test(is_superuser)
def organization_detail(request, organization_id):
    """View to show details of a specific organization"""
    organization = get_object_or_404(Organization, id=organization_id)
    
    # Get subscriptions for this organization
    subscriptions = organization.subscriptions.all()
    
    context = {
        'organization': organization,
        'subscriptions': subscriptions,
    }
    return render(request, 'superadmin/organization_detail.html', context)


# Audit Log Views
@login_required
@user_passes_test(is_superuser)
def audit_log_list(request):
    """View to list all audit logs"""
    audit_logs = AuditLog.objects.all().order_by('-timestamp')
    
    context = {
        'audit_logs': audit_logs,
    }
    return render(request, 'superadmin/audit_log_list.html', context)