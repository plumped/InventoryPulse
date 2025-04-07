from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.contrib.auth.models import User, Group, Permission

from inventory.models import Warehouse
from organization.models import Department
from .models import WarehouseAccess
from .decorators import permission_required, is_admin
from .forms import WarehouseAccessForm
from .permissions import PERMISSION_AREAS
from core.utils.logging_utils import log_list_view_usage
import logging

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
@user_passes_test(is_admin)
def warehouse_access_management(request):
    log_list_view_usage(request, view_name="warehouse_access_management")

    form = WarehouseAccessForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        access = form.save()
        action = 'created' if form.was_created() else 'updated'
        messages.success(request, f'Access rights for {access.department.name} to {access.warehouse.name} have been {action}.')
        return redirect('warehouse_access_management')

    access_rights = WarehouseAccess.objects.select_related('warehouse', 'department').all()

    context = {
        'form': form,
        'access_rights': access_rights,
    }

    return render(request, 'accessmanagement/warehouse_access_management.html', context)


@login_required
@user_passes_test(is_admin)
def warehouse_access_add(request):
    return _handle_warehouse_access_form(
        request,
        title='Add New Warehouse Access Rights',
        success_message='Access rights for department "{department}" to warehouse "{warehouse}" have been created.'
    )


@login_required
@user_passes_test(is_admin)
def warehouse_access_edit(request, pk):
    access = get_object_or_404(WarehouseAccess, pk=pk)
    return _handle_warehouse_access_form(
        request,
        instance=access,
        title=f'Edit Access Rights: {access.department.name} → {access.warehouse.name}',
        success_message='Access rights for department "{department}" to warehouse "{warehouse}" have been updated.'
    )


@login_required
@user_passes_test(is_admin)
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
@user_passes_test(is_admin)
def user_permissions_management(request):
    log_list_view_usage(request, view_name="user_permissions_management")

    users = User.objects.all().order_by('username')
    groups = Group.objects.all().order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        user = get_object_or_404(User, pk=user_id)

        if action == 'assign_group':
            group_id = request.POST.get('group_id')
            group = get_object_or_404(Group, pk=group_id)
            if request.POST.get('assign') == 'true':
                user.groups.add(group)
                messages.success(request, f'User {user.username} has been added to group {group.name}.')
            else:
                user.groups.remove(group)
                messages.success(request, f'User {user.username} has been removed from group {group.name}.')

        elif action == 'direct_permission':
            perm_id = request.POST.get('permission_id')
            perm = get_object_or_404(Permission, pk=perm_id)
            if request.POST.get('assign') == 'true':
                user.user_permissions.add(perm)
                messages.success(request, f'Permission {perm.name} has been directly assigned to {user.username}.')
            else:
                user.user_permissions.remove(perm)
                messages.success(request, f'Permission {perm.name} has been removed from {user.username}.')

    permissions = {
        area: Permission.objects.filter(codename__contains=f'_{area}').order_by('codename')
        for area in PERMISSION_AREAS.keys()
    }

    context = {
        'users': users,
        'groups': groups,
        'permissions': permissions,
        'permission_areas': PERMISSION_AREAS,
    }

    return render(request, 'accessmanagement/user_permissions_management.html', context)


@login_required
@user_passes_test(is_admin)
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
