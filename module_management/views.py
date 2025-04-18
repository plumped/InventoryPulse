from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from master_data.models.organisations_models import Organization
from .models import Module, FeatureFlag, SubscriptionPackage, Subscription


# Helper function to check if user is admin
def is_admin(user):
    return user.is_superuser or user.is_staff


# Module views
@login_required
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
    return render(request, 'module_management/module_list.html', context)


@login_required
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
    return render(request, 'module_management/module_detail.html', context)


@login_required
@user_passes_test(is_admin)
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

        messages.success(request, f'Module "{module.name}" created successfully.')
        return redirect('module_detail', module_id=module.id)

    return render(request, 'module_management/module_form.html', {'action': 'Create'})


@login_required
@user_passes_test(is_admin)
def module_update(request, module_id):
    """View to update an existing module"""
    module = get_object_or_404(Module, id=module_id)

    if request.method == 'POST':
        # Process form data
        module.name = request.POST.get('name')
        module.code = request.POST.get('code')
        module.description = request.POST.get('description')
        module.price_monthly = request.POST.get('price_monthly')
        module.price_yearly = request.POST.get('price_yearly')
        module.is_active = request.POST.get('is_active') == 'on'

        # Save module
        module.save()

        messages.success(request, f'Module "{module.name}" updated successfully.')
        return redirect('module_detail', module_id=module.id)

    context = {
        'module': module,
        'action': 'Update'
    }
    return render(request, 'module_management/module_form.html', context)


@login_required
@user_passes_test(is_admin)
def module_delete(request, module_id):
    """View to delete a module"""
    module = get_object_or_404(Module, id=module_id)

    if request.method == 'POST':
        module_name = module.name
        module.delete()
        messages.success(request, f'Module "{module_name}" deleted successfully.')
        return redirect('module_list')

    context = {
        'module': module,
    }
    return render(request, 'module_management/module_confirm_delete.html', context)


# Feature Flag views
@login_required
def feature_flag_list(request):
    """View to list all feature flags"""
    feature_flags = FeatureFlag.objects.all()

    # Filter by module if specified
    module_id = request.GET.get('module')
    if module_id:
        feature_flags = feature_flags.filter(module_id=module_id)
        module = get_object_or_404(Module, id=module_id)
    else:
        module = None

    context = {
        'feature_flags': feature_flags,
        'module': module,
        'active_flags': feature_flags.filter(is_active=True).count(),
        'total_flags': feature_flags.count(),
    }
    return render(request, 'module_management/feature_flag_list.html', context)


@login_required
def feature_flag_detail(request, flag_id):
    """View to show details of a specific feature flag"""
    feature_flag = get_object_or_404(FeatureFlag, id=flag_id)

    # Get packages that include this feature flag
    packages = feature_flag.subscription_packages.all()

    context = {
        'feature_flag': feature_flag,
        'packages': packages,
    }
    return render(request, 'module_management/feature_flag_detail.html', context)


@login_required
@user_passes_test(is_admin)
def feature_flag_create(request):
    """View to create a new feature flag"""
    # Get all modules for the form
    modules = Module.objects.all()

    if request.method == 'POST':
        # Process form data
        name = request.POST.get('name')
        code = request.POST.get('code')
        description = request.POST.get('description')
        module_id = request.POST.get('module')
        is_active = request.POST.get('is_active') == 'on'

        # Get module
        module = get_object_or_404(Module, id=module_id)

        # Create feature flag
        feature_flag = FeatureFlag.objects.create(
            name=name,
            code=code,
            description=description,
            module=module,
            is_active=is_active
        )

        messages.success(request, f'Feature flag "{feature_flag.name}" created successfully.')
        return redirect('feature_flag_detail', flag_id=feature_flag.id)

    context = {
        'modules': modules,
        'action': 'Create'
    }
    return render(request, 'module_management/feature_flag_form.html', context)


@login_required
@user_passes_test(is_admin)
def feature_flag_update(request, flag_id):
    """View to update an existing feature flag"""
    feature_flag = get_object_or_404(FeatureFlag, id=flag_id)
    modules = Module.objects.all()

    if request.method == 'POST':
        # Process form data
        feature_flag.name = request.POST.get('name')
        feature_flag.code = request.POST.get('code')
        feature_flag.description = request.POST.get('description')
        module_id = request.POST.get('module')
        feature_flag.module = get_object_or_404(Module, id=module_id)
        feature_flag.is_active = request.POST.get('is_active') == 'on'

        # Save feature flag
        feature_flag.save()

        messages.success(request, f'Feature flag "{feature_flag.name}" updated successfully.')
        return redirect('feature_flag_detail', flag_id=feature_flag.id)

    context = {
        'feature_flag': feature_flag,
        'modules': modules,
        'action': 'Update'
    }
    return render(request, 'module_management/feature_flag_form.html', context)


@login_required
@user_passes_test(is_admin)
def feature_flag_delete(request, flag_id):
    """View to delete a feature flag"""
    feature_flag = get_object_or_404(FeatureFlag, id=flag_id)

    if request.method == 'POST':
        flag_name = feature_flag.name
        feature_flag.delete()
        messages.success(request, f'Feature flag "{flag_name}" deleted successfully.')
        return redirect('feature_flag_list')

    context = {
        'feature_flag': feature_flag,
    }
    return render(request, 'module_management/feature_flag_confirm_delete.html', context)


# Subscription Package views
@login_required
def package_list(request):
    """View to list all subscription packages"""
    packages = SubscriptionPackage.objects.all()

    context = {
        'packages': packages,
        'active_packages': packages.filter(is_active=True).count(),
        'total_packages': packages.count(),
    }
    return render(request, 'module_management/package_list.html', context)


@login_required
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
    return render(request, 'module_management/package_detail.html', context)


@login_required
@user_passes_test(is_admin)
def package_create(request):
    """View to create a new subscription package"""
    # Get all modules and feature flags for the form
    modules = Module.objects.filter(is_active=True)
    feature_flags = FeatureFlag.objects.filter(is_active=True)

    if request.method == 'POST':
        # Process form data
        name = request.POST.get('name')
        code = request.POST.get('code')
        description = request.POST.get('description')
        price_monthly = request.POST.get('price_monthly')
        price_yearly = request.POST.get('price_yearly')
        is_active = request.POST.get('is_active') == 'on'

        # Create package
        package = SubscriptionPackage.objects.create(
            name=name,
            code=code,
            description=description,
            price_monthly=price_monthly,
            price_yearly=price_yearly,
            is_active=is_active
        )

        # Add modules
        module_ids = request.POST.getlist('modules')
        package.modules.set(Module.objects.filter(id__in=module_ids))

        # Add feature flags
        flag_ids = request.POST.getlist('feature_flags')
        package.feature_flags.set(FeatureFlag.objects.filter(id__in=flag_ids))

        messages.success(request, f'Subscription package "{package.name}" created successfully.')
        return redirect('package_detail', package_id=package.id)

    context = {
        'modules': modules,
        'feature_flags': feature_flags,
        'action': 'Create'
    }
    return render(request, 'module_management/package_form.html', context)


@login_required
@user_passes_test(is_admin)
def package_update(request, package_id):
    """View to update an existing subscription package"""
    package = get_object_or_404(SubscriptionPackage, id=package_id)
    modules = Module.objects.filter(is_active=True)
    feature_flags = FeatureFlag.objects.filter(is_active=True)

    if request.method == 'POST':
        # Process form data
        package.name = request.POST.get('name')
        package.code = request.POST.get('code')
        package.description = request.POST.get('description')
        package.price_monthly = request.POST.get('price_monthly')
        package.price_yearly = request.POST.get('price_yearly')
        package.is_active = request.POST.get('is_active') == 'on'

        # Save package
        package.save()

        # Update modules
        module_ids = request.POST.getlist('modules')
        package.modules.set(Module.objects.filter(id__in=module_ids))

        # Update feature flags
        flag_ids = request.POST.getlist('feature_flags')
        package.feature_flags.set(FeatureFlag.objects.filter(id__in=flag_ids))

        messages.success(request, f'Subscription package "{package.name}" updated successfully.')
        return redirect('package_detail', package_id=package.id)

    context = {
        'package': package,
        'modules': modules,
        'feature_flags': feature_flags,
        'action': 'Update'
    }
    return render(request, 'module_management/package_form.html', context)


@login_required
@user_passes_test(is_admin)
def package_delete(request, package_id):
    """View to delete a subscription package"""
    package = get_object_or_404(SubscriptionPackage, id=package_id)

    if request.method == 'POST':
        package_name = package.name
        package.delete()
        messages.success(request, f'Subscription package "{package_name}" deleted successfully.')
        return redirect('package_list')

    context = {
        'package': package,
    }
    return render(request, 'module_management/package_confirm_delete.html', context)


# Subscription views
@login_required
def subscription_list(request):
    """View to list all subscriptions"""
    subscriptions = Subscription.objects.all()

    # Filter by organization if specified
    organization_id = request.GET.get('organization')
    if organization_id:
        subscriptions = subscriptions.filter(organization_id=organization_id)
        organization = get_object_or_404(Organization, id=organization_id)
    else:
        organization = None

    # Filter by package if specified
    package_id = request.GET.get('package')
    if package_id:
        subscriptions = subscriptions.filter(package_id=package_id)
        package = get_object_or_404(SubscriptionPackage, id=package_id)
    else:
        package = None

    # Filter by status
    status = request.GET.get('status')
    if status == 'active':
        subscriptions = subscriptions.filter(is_active=True)
    elif status == 'inactive':
        subscriptions = subscriptions.filter(is_active=False)

    context = {
        'subscriptions': subscriptions,
        'organization': organization,
        'package': package,
        'status': status,
        'active_subscriptions': subscriptions.filter(is_active=True).count(),
        'total_subscriptions': subscriptions.count(),
    }
    return render(request, 'module_management/subscription_list.html', context)


@login_required
def subscription_detail(request, subscription_id):
    """View to show details of a specific subscription"""
    subscription = get_object_or_404(Subscription, id=subscription_id)

    # Get modules in this subscription (from package and custom)
    package_modules = subscription.package.modules.all()
    custom_modules = subscription.custom_modules.all()
    all_modules = (package_modules | custom_modules).distinct()

    # Get feature flags in this subscription (from package and custom)
    package_features = subscription.package.feature_flags.all()
    custom_features = subscription.custom_features.all()
    all_features = (package_features | custom_features).distinct()

    # Get custom settings
    custom_settings = subscription.get_custom_settings()

    context = {
        'subscription': subscription,
        'package_modules': package_modules,
        'custom_modules': custom_modules,
        'all_modules': all_modules,
        'package_features': package_features,
        'custom_features': custom_features,
        'all_features': all_features,
        'custom_settings': custom_settings,
    }
    return render(request, 'module_management/subscription_detail.html', context)


@login_required
@user_passes_test(is_admin)
def subscription_create(request):
    """View to create a new subscription"""
    # Get all organizations and packages for the form
    organizations = Organization.objects.all()
    packages = SubscriptionPackage.objects.filter(is_active=True)
    modules = Module.objects.filter(is_active=True)
    feature_flags = FeatureFlag.objects.filter(is_active=True)

    if request.method == 'POST':
        # Process form data
        organization_id = request.POST.get('organization')
        package_id = request.POST.get('package')
        subscription_type = request.POST.get('subscription_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        is_active = request.POST.get('is_active') == 'on'
        payment_status = request.POST.get('payment_status')
        custom_settings = request.POST.get('custom_settings', '{}')

        # Get organization and package
        organization = get_object_or_404(Organization, id=organization_id)
        package = get_object_or_404(SubscriptionPackage, id=package_id)

        # Create subscription
        subscription = Subscription.objects.create(
            organization=organization,
            package=package,
            subscription_type=subscription_type,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            payment_status=payment_status,
            custom_settings=custom_settings
        )

        # Add custom modules
        custom_module_ids = request.POST.getlist('custom_modules')
        subscription.custom_modules.set(Module.objects.filter(id__in=custom_module_ids))

        # Add custom feature flags
        custom_feature_ids = request.POST.getlist('custom_features')
        subscription.custom_features.set(FeatureFlag.objects.filter(id__in=custom_feature_ids))

        messages.success(request, f'Subscription for "{organization.name}" created successfully.')
        return redirect('subscription_detail', subscription_id=subscription.id)

    context = {
        'organizations': organizations,
        'packages': packages,
        'modules': modules,
        'feature_flags': feature_flags,
        'action': 'Create',
        'subscription_types': Subscription.SUBSCRIPTION_TYPE_CHOICES,
        'payment_statuses': Subscription.PAYMENT_STATUS_CHOICES,
    }
    return render(request, 'module_management/subscription_form.html', context)


@login_required
@user_passes_test(is_admin)
def subscription_update(request, subscription_id):
    """View to update an existing subscription"""
    subscription = get_object_or_404(Subscription, id=subscription_id)
    organizations = Organization.objects.all()
    packages = SubscriptionPackage.objects.filter(is_active=True)
    modules = Module.objects.filter(is_active=True)
    feature_flags = FeatureFlag.objects.filter(is_active=True)

    if request.method == 'POST':
        # Process form data
        organization_id = request.POST.get('organization')
        package_id = request.POST.get('package')
        subscription.organization = get_object_or_404(Organization, id=organization_id)
        subscription.package = get_object_or_404(SubscriptionPackage, id=package_id)
        subscription.subscription_type = request.POST.get('subscription_type')
        subscription.start_date = request.POST.get('start_date')
        subscription.end_date = request.POST.get('end_date')
        subscription.is_active = request.POST.get('is_active') == 'on'
        subscription.payment_status = request.POST.get('payment_status')
        subscription.custom_settings = request.POST.get('custom_settings', '{}')

        # Save subscription
        subscription.save()

        # Update custom modules
        custom_module_ids = request.POST.getlist('custom_modules')
        subscription.custom_modules.set(Module.objects.filter(id__in=custom_module_ids))

        # Update custom feature flags
        custom_feature_ids = request.POST.getlist('custom_features')
        subscription.custom_features.set(FeatureFlag.objects.filter(id__in=custom_feature_ids))

        messages.success(request, f'Subscription for "{subscription.organization.name}" updated successfully.')
        return redirect('subscription_detail', subscription_id=subscription.id)

    context = {
        'subscription': subscription,
        'organizations': organizations,
        'packages': packages,
        'modules': modules,
        'feature_flags': feature_flags,
        'action': 'Update',
        'subscription_types': Subscription.SUBSCRIPTION_TYPE_CHOICES,
        'payment_statuses': Subscription.PAYMENT_STATUS_CHOICES,
    }
    return render(request, 'module_management/subscription_form.html', context)


@login_required
@user_passes_test(is_admin)
def subscription_delete(request, subscription_id):
    """View to delete a subscription"""
    subscription = get_object_or_404(Subscription, id=subscription_id)

    if request.method == 'POST':
        org_name = subscription.organization.name if subscription.organization else "Unknown"
        subscription.delete()
        messages.success(request, f'Subscription for "{org_name}" deleted successfully.')
        return redirect('subscription_list')

    context = {
        'subscription': subscription,
    }
    return render(request, 'module_management/subscription_confirm_delete.html', context)


# API views for AJAX
@login_required
def get_package_details(request, package_id):
    """API view to get details of a package for AJAX requests"""
    package = get_object_or_404(SubscriptionPackage, id=package_id)

    # Get modules in this package
    modules = list(package.modules.values('id', 'name'))

    # Get feature flags in this package
    feature_flags = list(package.feature_flags.values('id', 'name'))

    data = {
        'id': package.id,
        'name': package.name,
        'code': package.code,
        'description': package.description,
        'price_monthly': float(package.price_monthly),
        'price_yearly': float(package.price_yearly),
        'is_active': package.is_active,
        'modules': modules,
        'feature_flags': feature_flags,
    }

    return JsonResponse(data)


@login_required
def check_module_access(request, module_code):
    """API view to check if the current user has access to a module"""
    try:
        # Check if the module exists
        module = Module.objects.get(code=module_code)

        # Check if the user has access
        has_access = False

        # Superusers always have access
        if request.user.is_superuser:
            has_access = True
        else:
            # Get the user's organization
            # This is a simplified version - in a real app, you'd need to determine the user's organization
            user_organizations = Organization.objects.filter(
                Q(admin_users=request.user) |
                Q(departments__members=request.user) |
                Q(departments__manager=request.user)
            ).distinct()

            # Check if any of the user's organizations have a subscription that includes this module
            for org in user_organizations:
                subscriptions = Subscription.objects.filter(
                    organization=org,
                    is_active=True
                )

                for subscription in subscriptions:
                    if subscription.has_module_access(module_code):
                        has_access = True
                        break

                if has_access:
                    break

        return JsonResponse({
            'module': module_code,
            'has_access': has_access,
            'module_name': module.name,
        })

    except Module.DoesNotExist:
        return JsonResponse({
            'module': module_code,
            'has_access': False,
            'error': 'Module does not exist',
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'module': module_code,
            'has_access': False,
            'error': str(e),
        }, status=500)


@login_required
def check_feature_access(request, feature_code):
    """API view to check if the current user has access to a feature"""
    try:
        # Check if the feature exists
        feature = FeatureFlag.objects.get(code=feature_code)

        # Check if the user has access
        has_access = False

        # Superusers always have access
        if request.user.is_superuser:
            has_access = True
        else:
            # Get the user's organization
            # This is a simplified version - in a real app, you'd need to determine the user's organization
            user_organizations = Organization.objects.filter(
                Q(admin_users=request.user) |
                Q(departments__members=request.user) |
                Q(departments__manager=request.user)
            ).distinct()

            # Check if any of the user's organizations have a subscription that includes this feature
            for org in user_organizations:
                subscriptions = Subscription.objects.filter(
                    organization=org,
                    is_active=True
                )

                for subscription in subscriptions:
                    if subscription.has_feature_access(feature_code):
                        has_access = True
                        break

                if has_access:
                    break

        return JsonResponse({
            'feature': feature_code,
            'has_access': has_access,
            'feature_name': feature.name,
            'module': feature.module.code,
            'module_name': feature.module.name,
        })

    except FeatureFlag.DoesNotExist:
        return JsonResponse({
            'feature': feature_code,
            'has_access': False,
            'error': 'Feature does not exist',
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'feature': feature_code,
            'has_access': False,
            'error': str(e),
        }, status=500)
