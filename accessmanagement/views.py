# accessmanagement/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.models import User, Group, Permission

from inventory.models import Warehouse
from organization.models import Department
from .models import WarehouseAccess
from .decorators import permission_required, is_admin
from .forms import WarehouseAccessForm


@login_required
@permission_required('inventory', 'admin')
def warehouse_access_management(request):
    """Manage warehouse access rights."""
    # Only administrators can manage access rights
    if not is_admin(request.user):
        return HttpResponseForbidden("Only administrators can manage warehouse access rights.")

    warehouses = Warehouse.objects.filter(is_active=True)
    departments = Department.objects.all()

    if request.method == 'POST':
        warehouse_id = request.POST.get('warehouse')
        department_id = request.POST.get('department')

        can_view = request.POST.get('can_view') == 'on'
        can_edit = request.POST.get('can_edit') == 'on'
        can_manage_stock = request.POST.get('can_manage_stock') == 'on'

        if warehouse_id and department_id:
            warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
            department = get_object_or_404(Department, pk=department_id)

            # Create or update access right
            access, created = WarehouseAccess.objects.update_or_create(
                warehouse=warehouse,
                department=department,
                defaults={
                    'can_view': can_view,
                    'can_edit': can_edit,
                    'can_manage_stock': can_manage_stock,
                }
            )

            if created:
                messages.success(request, f'Access rights for {department.name} to {warehouse.name} have been created.')
            else:
                messages.success(request, f'Access rights for {department.name} to {warehouse.name} have been updated.')

            return redirect('warehouse_access_management')

    # Get existing access rights
    access_rights = WarehouseAccess.objects.select_related('warehouse', 'department').all()

    context = {
        'warehouses': warehouses,
        'departments': departments,
        'access_rights': access_rights,
    }

    return render(request, 'accessmanagement/warehouse_access_management.html', context)


@login_required
@permission_required('inventory', 'admin')
def warehouse_access_add(request):
    """Add new warehouse access rights."""
    # Only administrators can manage access rights
    if not is_admin(request.user):
        return HttpResponseForbidden("Only administrators can manage warehouse access rights.")

    if request.method == 'POST':
        form = WarehouseAccessForm(request.POST)
        if form.is_valid():
            access = form.save()
            messages.success(
                request,
                f'Access rights for department "{access.department.name}" to warehouse "{access.warehouse.name}" have been created.'
            )
            return redirect('warehouse_access_management')
    else:
        form = WarehouseAccessForm()

    context = {
        'form': form,
        'title': 'Add New Warehouse Access Rights',
    }

    return render(request, 'accessmanagement/warehouse_access_form.html', context)


@login_required
@permission_required('inventory', 'admin')
def warehouse_access_edit(request, pk):
    """Edit warehouse access rights."""
    access = get_object_or_404(WarehouseAccess, pk=pk)

    # Only administrators can manage access rights
    if not is_admin(request.user):
        return HttpResponseForbidden("Only administrators can manage warehouse access rights.")

    if request.method == 'POST':
        form = WarehouseAccessForm(request.POST, instance=access)
        if form.is_valid():
            access = form.save()
            messages.success(
                request,
                f'Access rights for department "{access.department.name}" to warehouse "{access.warehouse.name}" have been updated.'
            )
            return redirect('warehouse_access_management')
    else:
        form = WarehouseAccessForm(instance=access)

    context = {
        'form': form,
        'access': access,
        'title': f'Edit Access Rights: {access.department.name} → {access.warehouse.name}',
    }

    return render(request, 'accessmanagement/warehouse_access_form.html', context)


@login_required
@permission_required('inventory', 'admin')
def warehouse_access_delete(request, pk):
    """Delete warehouse access rights."""
    access = get_object_or_404(WarehouseAccess, pk=pk)

    # Only administrators can manage access rights
    if not is_admin(request.user):
        return HttpResponseForbidden("Only administrators can manage warehouse access rights.")

    if request.method == 'POST':
        warehouse_name = access.warehouse.name
        department_name = access.department.name
        access.delete()
        messages.success(request, f'Access rights for {department_name} to {warehouse_name} have been deleted.')
        return redirect('warehouse_access_management')

    context = {
        'access': access,
    }

    return render(request, 'accessmanagement/warehouse_access_confirm_delete.html', context)


@login_required
@permission_required('inventory', 'admin')
def user_permissions_management(request):
    """Manage user permissions."""
    # Only administrators can manage permissions
    if not is_admin(request.user):
        return HttpResponseForbidden("Only administrators can manage user permissions.")

    users = User.objects.all().order_by('username')
    groups = Group.objects.all().order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'assign_group':
            user_id = request.POST.get('user_id')
            group_id = request.POST.get('group_id')

            try:
                user = User.objects.get(pk=user_id)
                group = Group.objects.get(pk=group_id)

                if request.POST.get('assign') == 'true':
                    user.groups.add(group)
                    messages.success(request, f'User {user.username} has been added to group {group.name}.')
                else:
                    user.groups.remove(group)
                    messages.success(request, f'User {user.username} has been removed from group {group.name}.')

            except (User.DoesNotExist, Group.DoesNotExist):
                messages.error(request, "User or group not found.")

        elif action == 'direct_permission':
            user_id = request.POST.get('user_id')
            perm_id = request.POST.get('permission_id')

            try:
                user = User.objects.get(pk=user_id)
                perm = Permission.objects.get(pk=perm_id)

                if request.POST.get('assign') == 'true':
                    user.user_permissions.add(perm)
                    messages.success(request, f'Permission {perm.name} has been directly assigned to {user.username}.')
                else:
                    user.user_permissions.remove(perm)
                    messages.success(request, f'Permission {perm.name} has been removed from {user.username}.')

            except (User.DoesNotExist, Permission.DoesNotExist):
                messages.error(request, "User or permission not found.")

    from .permissions import PERMISSION_AREAS
    # Group permissions by area
    permissions = {}
    for area in PERMISSION_AREAS.keys():
        area_perms = Permission.objects.filter(codename__contains=f'_{area}').order_by('codename')
        permissions[area] = area_perms

    context = {
        'users': users,
        'groups': groups,
        'permissions': permissions,
        'permission_areas': PERMISSION_AREAS,
    }

    return render(request, 'accessmanagement/user_permissions_management.html', context)


@login_required
def get_user_permissions(request):
    """AJAX endpoint to get user permissions."""
    user_id = request.GET.get('user_id')

    try:
        user = User.objects.get(pk=user_id)

        # Groups
        groups = list(user.groups.values_list('id', flat=True))

        # Direct permissions
        direct_permissions = list(user.user_permissions.values_list('id', flat=True))

        # Effective permissions (including from groups)
        effective_permissions = []

        # From groups
        for group in user.groups.all():
            for perm in group.permissions.all():
                effective_permissions.append({
                    'id': perm.id,
                    'name': perm.name,
                    'codename': perm.codename,
                    'source': f'Group: {group.name}'
                })

        # Direct
        for perm in user.user_permissions.all():
            effective_permissions.append({
                'id': perm.id,
                'name': perm.name,
                'codename': perm.codename,
                'source': 'Directly assigned'
            })

        return JsonResponse({
            'groups': groups,
            'direct_permissions': direct_permissions,
            'effective_permissions': effective_permissions
        })

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)