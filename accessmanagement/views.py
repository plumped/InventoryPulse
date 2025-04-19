import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group, Permission
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from admin_dashboard.forms import WarehouseAccessForm
from core.utils.logging_utils import log_list_view_usage
from .forms import RegistrationForm
from .models import WarehouseAccess

logger = logging.getLogger(__name__)


def _handle_warehouse_access_form(request, instance=None, title='', success_message=''):
    if request.method == 'POST':
        form = WarehouseAccessForm(request.POST, instance=instance)
        if form.is_valid():
            access = form.save()
            messages.success(request, success_message.format(
                department=access.department.name,
                warehouse=access.warehouse.name
            ))
            return redirect('warehouse_access_management')
    else:
        form = WarehouseAccessForm(instance=instance)

    context = {
        'form': form,
        'access': instance,
        'title': title,
    }
    return render(request, 'accessmanagement/warehouse_access_form.html', context)


@login_required
@permission_required('accessmanagement.view_warehouseaccess', raise_exception=True)
def warehouse_access_management(request):
    log_list_view_usage(request, view_name="warehouse_access_management")

    form = WarehouseAccessForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        access = form.save()
        action = 'created' if form.was_created() else 'updated'
        messages.success(request,
                         f'Access rights for {access.department.name} to {access.warehouse.name} have been {action}.')
        return redirect('warehouse_access_management')

    access_rights = WarehouseAccess.objects.select_related('warehouse', 'department').all()

    context = {
        'form': form,
        'access_rights': access_rights,
    }

    return render(request, 'accessmanagement/warehouse_access_management.html', context)


@login_required
@permission_required('accessmanagement.add_warehouseaccess', raise_exception=True)
def warehouse_access_add(request):
    return _handle_warehouse_access_form(
        request,
        title='Add New Warehouse Access Rights',
        success_message='Access rights for department "{department}" to warehouse "{warehouse}" have been created.'
    )


@login_required
@permission_required('accessmanagement.change_warehouseaccess', raise_exception=True)
def warehouse_access_edit(request, pk):
    access = get_object_or_404(WarehouseAccess, pk=pk)
    return _handle_warehouse_access_form(
        request,
        instance=access,
        title=f'Edit Access Rights: {access.department.name} → {access.warehouse.name}',
        success_message='Access rights for department "{department}" to warehouse "{warehouse}" have been updated.'
    )


@login_required
@permission_required('accessmanagement.delete_warehouseaccess', raise_exception=True)
def warehouse_access_delete(request, pk):
    access = get_object_or_404(WarehouseAccess, pk=pk)

    if request.method == 'POST':
        warehouse_name = access.warehouse.name
        department_name = access.department.name
        access.delete()
        messages.success(request, f'Access rights for {department_name} to {warehouse_name} have been deleted.')
        return redirect('warehouse_access_management')

    return render(request, 'accessmanagement/warehouse_access_confirm_delete.html', {'access': access})


@login_required
@permission_required('auth.view_user', raise_exception=True)
def user_permissions_management(request):
    log_list_view_usage(request, view_name="user_permissions_management")

    users = User.objects.all().order_by('username')
    groups = Group.objects.all().order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        user = get_object_or_404(User, pk=user_id)

        if action == 'assign_group':
            if not request.user.has_perm('auth.change_user'):
                return JsonResponse({'error': 'Permission denied'}, status=403)

            group_id = request.POST.get('group_id')
            group = get_object_or_404(Group, pk=group_id)
            if request.POST.get('assign') == 'true':
                user.groups.add(group)
                messages.success(request, f'User {user.username} has been added to group {group.name}.')
            else:
                user.groups.remove(group)
                messages.success(request, f'User {user.username} has been removed from group {group.name}.')

        elif action == 'direct_permission':
            if not request.user.has_perm('auth.change_user'):
                return JsonResponse({'error': 'Permission denied'}, status=403)

            perm_id = request.POST.get('permission_id')
            perm = get_object_or_404(Permission, pk=perm_id)
            if request.POST.get('assign') == 'true':
                user.user_permissions.add(perm)
                messages.success(request, f'Permission {perm.name} has been directly assigned to {user.username}.')
            else:
                user.user_permissions.remove(perm)
                messages.success(request, f'Permission {perm.name} has been removed from {user.username}.')

    # Gruppiere Berechtigungen nach Content-Type (App + Model)
    from django.contrib.contenttypes.models import ContentType

    # Berechtigungen nach Content-Type gruppieren
    content_types = ContentType.objects.all().order_by('app_label', 'model')
    permissions_by_content_type = {}

    for ct in content_types:
        perms = Permission.objects.filter(content_type=ct).order_by('codename')
        if perms.exists():  # Nur Content-Types mit Berechtigungen hinzufügen
            app_name = ct.app_label.replace('_', ' ').title()
            model_name = ct.model.replace('_', ' ').title()
            key = f"{ct.app_label}.{ct.model}"

            permissions_by_content_type[key] = {
                'name': f"{app_name} - {model_name}",
                'permissions': perms
            }

    context = {
        'users': users,
        'groups': groups,
        'permissions_by_content_type': permissions_by_content_type,
    }

    return render(request, 'accessmanagement/user_permissions_management.html', context)



@login_required
@permission_required('auth.view_user', raise_exception=True)
def get_user_permissions(request):
    user_id = request.GET.get('user_id')
    try:
        user = User.objects.get(pk=user_id)

        groups = list(user.groups.values_list('id', flat=True))
        direct_permissions = list(user.user_permissions.values_list('id', flat=True))

        effective_permissions = [
                                    {
                                        'id': perm.id,
                                        'name': perm.name,
                                        'codename': perm.codename,
                                        'source': f'Group: {group.name}'
                                    }
                                    for group in user.groups.all()
                                    for perm in group.permissions.all()
                                ] + [
                                    {
                                        'id': perm.id,
                                        'name': perm.name,
                                        'codename': perm.codename,
                                        'source': 'Directly assigned'
                                    }
                                    for perm in user.user_permissions.all()
                                ]

        return JsonResponse({
            'groups': groups,
            'direct_permissions': direct_permissions,
            'effective_permissions': effective_permissions
        })

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)


def register(request):
    """
    View for user registration.
    Creates a new user account, associated company, and sets up tenant isolation.
    """
    # If user is already authenticated, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard/')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Create user, organization, and subscription
                user = form.save()

                # Get the user's organization
                try:
                    # Check if user has a profile
                    if hasattr(user, 'profile'):
                        organization = user.profile.organization

                        # Log organization details for debugging
                        logger.info(f"User {user.username} has profile with organization: {organization}")

                        # Set the current tenant context if organization exists
                        if organization:
                            from core.middleware import TenantMiddleware
                            TenantMiddleware.set_tenant(organization)
                        else:
                            logger.warning(f"User {user.username} has profile but organization is None")
                    else:
                        logger.warning(f"User {user.username} does not have a profile")
                        organization = None
                except Exception as e:
                    logger.error(f"Error getting organization for user {user.username}: {str(e)}")
                    organization = None

                # Log the user in
                login(request, user)

                # Add success message with organization and subscription details
                if organization:
                    messages.success(
                        request,
                        f'Welcome to InventoryPulse, {organization.name}! '
                        f'Your account has been created successfully and your free 10-day trial has started. '
                        f'After the trial period, you will need to subscribe to a paid plan. '
                        f'You can access your dashboard at {organization.subdomain}.inventorypulse.com'
                    )
                else:
                    messages.success(
                        request,
                        f'Welcome to InventoryPulse! '
                        f'Your account has been created successfully and your free 10-day trial has started. '
                        f'After the trial period, you will need to subscribe to a paid plan.'
                    )

                return redirect('dashboard')
            except Exception as e:
                # Log the error
                logger.error(f"Error during registration: {str(e)}")

                # Show error message to user
                messages.error(
                    request,
                    "There was an error creating your account. Please try again or contact support."
                )

                # If the user was created but something else failed, we should delete the user
                # to prevent orphaned accounts
                if 'user' in locals() and user.pk:
                    try:
                        user.delete()
                    except Exception:
                        pass
    else:
        form = RegistrationForm()

    return render(request, 'auth/register.html', {'form': form})
