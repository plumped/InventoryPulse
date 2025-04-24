import logging
import os
from datetime import datetime

from django.apps import apps
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from accessmanagement.models import WarehouseAccess, ObjectPermission, RoleHierarchy
from core.models import Warehouse
from core.utils.logging_utils import log_list_view_usage
from core.utils.pagination import paginate_queryset
from master_data.models.organisations_models import Department
from .forms import ObjectPermissionForm, RoleHierarchyForm, TimeBasedPermissionForm, WarehouseAccessForm

logger = logging.getLogger('admin_dashboard')

@login_required
@permission_required('accessmanagement.view_permission_dashboard', raise_exception=True)
def permissions_dashboard(request):
    """Main permissions dashboard view."""
    log_list_view_usage(request, view_name="permissions_dashboard")

    # Get statistics for the dashboard
    stats = {
        'user_count': User.objects.count(),
        'group_count': Group.objects.count(),
        'department_count': Department.objects.count(),
        'warehouse_access_count': WarehouseAccess.objects.count(),
        'object_permission_count': ObjectPermission.objects.count(),
        'role_hierarchy_count': RoleHierarchy.objects.count(),
    }

    # Get recent permission changes
    recent_object_permissions = ObjectPermission.objects.all().order_by('-id')[:10]
    recent_warehouse_access = WarehouseAccess.objects.all().order_by('-id')[:10]

    context = {
        'stats': stats,
        'recent_object_permissions': recent_object_permissions,
        'recent_warehouse_access': recent_warehouse_access,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/dashboard.html', context)

@login_required
@staff_member_required
@permission_required('auth.view_user', raise_exception=True)
def user_permissions(request, user_id):
    """View all permissions for a specific user."""
    log_list_view_usage(request, view_name="user_permissions")

    user = get_object_or_404(User, pk=user_id)

    # Get user's groups
    groups = user.groups.all()

    # Get user's direct permissions
    direct_permissions = user.user_permissions.all()

    # Get permissions from groups
    group_permissions = {}
    for group in groups:
        group_permissions[group.name] = group.permissions.all()

    # Get user's departments
    try:
        departments = user.profile.departments.all()
    except:
        departments = []

    # Get warehouse access
    warehouse_access = []
    for department in departments:
        access_rights = WarehouseAccess.objects.filter(department=department)
        for access in access_rights:
            warehouse_access.append({
                'warehouse': access.warehouse,
                'department': department,
                'can_view': access.can_view,
                'can_edit': access.can_edit,
                'can_manage_stock': access.can_manage_stock,
            })

    # Get object permissions
    object_permissions = ObjectPermission.objects.filter(
        Q(user=user) | Q(department__in=departments)
    ).select_related('content_type')

    # Get inherited permissions through role hierarchy
    inherited_permissions = []
    for group in groups:
        parent_roles = RoleHierarchy.get_all_parent_roles(group)
        for role in parent_roles:
            for perm in role.permissions.all():
                inherited_permissions.append({
                    'permission': perm,
                    'source': f'Inherited from {role.name} (parent of {group.name})'
                })

    context = {
        'user_obj': user,
        'groups': groups,
        'direct_permissions': direct_permissions,
        'group_permissions': group_permissions,
        'departments': departments,
        'warehouse_access': warehouse_access,
        'object_permissions': object_permissions,
        'inherited_permissions': inherited_permissions,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/user_permissions.html', context)

@login_required
@permission_required('accessmanagement.view_objectpermission', raise_exception=True)
def object_permissions(request):
    """View and manage object permissions."""
    log_list_view_usage(request, view_name="object_permissions")

    # Get filters from request
    filters = {
        'search': request.GET.get('search', ''),
        'content_type': request.GET.get('content_type', ''),
        'user': request.GET.get('user', ''),
        'department': request.GET.get('department', ''),
    }

    # Get all object permissions
    permissions = ObjectPermission.objects.all().select_related(
        'content_type', 'user', 'department'
    )

    # Apply filters
    if filters['search']:
        permissions = permissions.filter(
            Q(user__username__icontains=filters['search']) |
            Q(department__name__icontains=filters['search']) |
            Q(content_type__model__icontains=filters['search'])
        )

    if filters['content_type']:
        permissions = permissions.filter(content_type__id=filters['content_type'])

    if filters['user']:
        permissions = permissions.filter(user__id=filters['user'])

    if filters['department']:
        permissions = permissions.filter(department__id=filters['department'])

    # Paginate results
    page = request.GET.get('page')
    permissions_page = paginate_queryset(permissions, page, per_page=20)

    # Get content types for filter
    content_types = ContentType.objects.all().order_by('app_label', 'model')

    context = {
        'permissions': permissions_page,
        'filters': filters,
        'content_types': content_types,
        'users': User.objects.all(),
        'departments': Department.objects.all(),
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/object_permissions.html', context)

@login_required
@permission_required('accessmanagement.add_objectpermission', raise_exception=True)
def object_permission_add(request):
    """Add a new object permission."""
    if request.method == 'POST':
        form = ObjectPermissionForm(request.POST)
        if form.is_valid():
            permission = form.save()
            messages.success(request, 'Object permission added successfully.')
            return redirect('admin_object_permissions')
    else:
        form = ObjectPermissionForm()

    context = {
        'form': form,
        'title': 'Add Object Permission',
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/object_permission_form.html', context)

@login_required
@permission_required('accessmanagement.change_objectpermission', raise_exception=True)
def object_permission_edit(request, pk):
    """Edit an existing object permission."""
    permission = get_object_or_404(ObjectPermission, pk=pk)

    if request.method == 'POST':
        form = ObjectPermissionForm(request.POST, instance=permission)
        if form.is_valid():
            form.save()
            messages.success(request, 'Object permission updated successfully.')
            return redirect('admin_object_permissions')
    else:
        form = ObjectPermissionForm(instance=permission)

    context = {
        'form': form,
        'permission': permission,
        'title': 'Edit Object Permission',
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/object_permission_form.html', context)

@login_required
@permission_required('accessmanagement.delete_objectpermission', raise_exception=True)
def object_permission_delete(request, pk):
    """Delete an object permission."""
    permission = get_object_or_404(ObjectPermission, pk=pk)

    if request.method == 'POST':
        permission.delete()
        messages.success(request, 'Object permission deleted successfully.')
        return redirect('admin_object_permissions')

    context = {
        'permission': permission,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/object_permission_confirm_delete.html', context)

@login_required
@permission_required('accessmanagement.view_rolehierarchy', raise_exception=True)
def role_hierarchy(request):
    """View and manage role hierarchy."""
    log_list_view_usage(request, view_name="role_hierarchy")

    # Get all role hierarchies
    hierarchies = RoleHierarchy.objects.all().select_related('parent_role', 'child_role')

    context = {
        'hierarchies': hierarchies,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/role_hierarchy.html', context)

@login_required
@permission_required('accessmanagement.add_rolehierarchy', raise_exception=True)
def role_hierarchy_add(request):
    """Add a new role hierarchy."""
    if request.method == 'POST':
        form = RoleHierarchyForm(request.POST)
        if form.is_valid():
            hierarchy = form.save()
            messages.success(request, f'Role hierarchy {hierarchy.parent_role.name} -> {hierarchy.child_role.name} added successfully.')
            return redirect('admin_role_hierarchy')
    else:
        form = RoleHierarchyForm()

    context = {
        'form': form,
        'title': 'Add Role Hierarchy',
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/role_hierarchy_form.html', context)

@login_required
@permission_required('accessmanagement.change_rolehierarchy', raise_exception=True)
def role_hierarchy_edit(request, pk):
    """Edit an existing role hierarchy."""
    hierarchy = get_object_or_404(RoleHierarchy, pk=pk)

    if request.method == 'POST':
        form = RoleHierarchyForm(request.POST, instance=hierarchy)
        if form.is_valid():
            hierarchy = form.save()
            messages.success(request, f'Role hierarchy {hierarchy.parent_role.name} -> {hierarchy.child_role.name} updated successfully.')
            return redirect('admin_role_hierarchy')
    else:
        form = RoleHierarchyForm(instance=hierarchy)

    context = {
        'form': form,
        'hierarchy': hierarchy,
        'title': 'Edit Role Hierarchy',
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/role_hierarchy_form.html', context)

@login_required
@permission_required('accessmanagement.delete_rolehierarchy', raise_exception=True)
def role_hierarchy_delete(request, pk):
    """Delete a role hierarchy."""
    hierarchy = get_object_or_404(RoleHierarchy, pk=pk)

    if request.method == 'POST':
        parent_name = hierarchy.parent_role.name
        child_name = hierarchy.child_role.name
        hierarchy.delete()
        messages.success(request, f'Role hierarchy {parent_name} -> {child_name} deleted successfully.')
        return redirect('admin_role_hierarchy')

    context = {
        'hierarchy': hierarchy,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/role_hierarchy_confirm_delete.html', context)

@login_required
@permission_required('accessmanagement.view_objectpermission', raise_exception=True)
def time_based_permissions(request):
    """View and manage time-based permissions."""
    log_list_view_usage(request, view_name="time_based_permissions")

    # Get all time-based permissions (ObjectPermissions with valid_from or valid_until)
    permissions = ObjectPermission.objects.filter(
        Q(valid_from__isnull=False) | Q(valid_until__isnull=False)
    ).select_related('content_type', 'user', 'department')

    context = {
        'permissions': permissions,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/time_based_permissions.html', context)

@login_required
@permission_required('accessmanagement.add_objectpermission', raise_exception=True)
def time_based_permission_add(request):
    """Add a new time-based permission."""
    if request.method == 'POST':
        form = TimeBasedPermissionForm(request.POST)
        if form.is_valid():
            permission = form.save()
            messages.success(request, 'Time-based permission added successfully.')
            return redirect('admin_time_based_permissions')
    else:
        form = TimeBasedPermissionForm()

    context = {
        'form': form,
        'title': 'Add Time-Based Permission',
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/time_based_permission_form.html', context)

@login_required
@permission_required('accessmanagement.change_objectpermission', raise_exception=True)
def time_based_permission_edit(request, pk):
    """Edit an existing time-based permission."""
    permission = get_object_or_404(ObjectPermission, pk=pk)

    if request.method == 'POST':
        form = TimeBasedPermissionForm(request.POST, instance=permission)
        if form.is_valid():
            form.save()
            messages.success(request, 'Time-based permission updated successfully.')
            return redirect('admin_time_based_permissions')
    else:
        form = TimeBasedPermissionForm(instance=permission)

    context = {
        'form': form,
        'permission': permission,
        'title': 'Edit Time-Based Permission',
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/time_based_permission_form.html', context)

@login_required
@permission_required('accessmanagement.delete_objectpermission', raise_exception=True)
def time_based_permission_delete(request, pk):
    """Delete a time-based permission."""
    permission = get_object_or_404(ObjectPermission, pk=pk)

    if request.method == 'POST':
        permission.delete()
        messages.success(request, 'Time-based permission deleted successfully.')
        return redirect('admin_time_based_permissions')

    context = {
        'permission': permission,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/time_based_permission_confirm_delete.html', context)

@login_required
@permission_required('accessmanagement.view_warehouseaccess', raise_exception=True)
def warehouse_access(request):
    """View and manage warehouse access."""
    log_list_view_usage(request, view_name="warehouse_access")

    # Get all warehouse access
    access_rights = WarehouseAccess.objects.all().select_related('warehouse', 'department')

    # Get all warehouses and departments for the matrix view
    warehouses = Warehouse.objects.all()
    departments = Department.objects.all()

    context = {
        'access_rights': access_rights,
        'warehouses': warehouses,
        'departments': departments,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/warehouse_access.html', context)

@login_required
@permission_required('accessmanagement.add_warehouseaccess', raise_exception=True)
def warehouse_access_add(request):
    """Add new warehouse access."""
    if request.method == 'POST':
        form = WarehouseAccessForm(request.POST)
        if form.is_valid():
            access = form.save()
            messages.success(request, f'Access rights for {access.department.name} to {access.warehouse.name} added successfully.')
            return redirect('admin_warehouse_access')
    else:
        form = WarehouseAccessForm()

    context = {
        'form': form,
        'title': 'Add Warehouse Access',
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/warehouse_access_form.html', context)

@login_required
@permission_required('accessmanagement.change_warehouseaccess', raise_exception=True)
def warehouse_access_edit(request, pk):
    """Edit existing warehouse access."""
    access = get_object_or_404(WarehouseAccess, pk=pk)

    if request.method == 'POST':
        form = WarehouseAccessForm(request.POST, instance=access)
        if form.is_valid():
            access = form.save()
            messages.success(request, f'Access rights for {access.department.name} to {access.warehouse.name} updated successfully.')
            return redirect('admin_warehouse_access')
    else:
        form = WarehouseAccessForm(instance=access)

    context = {
        'form': form,
        'access': access,
        'title': 'Edit Warehouse Access',
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/warehouse_access_form.html', context)

@login_required
@permission_required('accessmanagement.delete_warehouseaccess', raise_exception=True)
def warehouse_access_delete(request, pk):
    """Delete warehouse access."""
    access = get_object_or_404(WarehouseAccess, pk=pk)

    if request.method == 'POST':
        department_name = access.department.name
        warehouse_name = access.warehouse.name
        access.delete()
        messages.success(request, f'Access rights for {department_name} to {warehouse_name} deleted successfully.')
        return redirect('admin_warehouse_access')

    context = {
        'access': access,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/warehouse_access_confirm_delete.html', context)

@login_required
@permission_required('auth.view_permission', raise_exception=True)
def permission_audit(request):
    """View permission audit reports."""
    log_list_view_usage(request, view_name="permission_audit")

    # Get the output directory for permission review reports
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'permission_review')

    # Check if the directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Get all CSV files in the directory
    reports = []
    if os.path.exists(output_dir):
        for file in os.listdir(output_dir):
            if file.endswith('.csv'):
                file_path = os.path.join(output_dir, file)
                reports.append({
                    'name': file,
                    'path': file,  # Just store the filename, not the full path
                    'size': os.path.getsize(file_path),
                    'date': datetime.fromtimestamp(os.path.getmtime(file_path)),
                })

    # Sort reports by date (newest first)
    reports.sort(key=lambda x: x['date'], reverse=True)

    context = {
        'reports': reports,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/permission_audit.html', context)

@login_required
@permission_required('auth.view_permission', raise_exception=True)
def run_permission_audit(request):
    """Run the permission audit command."""
    try:
        # Run the management command
        from django.core.management import call_command

        # Get parameters from request
        try:
            inactive_days = int(request.POST.get('inactive_days', 90))
        except ValueError:
            # Handle case where inactive_days is not a valid integer
            logger.warning(f"Invalid inactive_days value: {request.POST.get('inactive_days')}. Using default of 90.")
            inactive_days = 90
        output_format = request.POST.get('format', 'csv')

        # Call the command
        call_command('review_permissions', inactive_days=inactive_days, format=output_format)

        messages.success(request, 'Permission audit completed successfully.')
    except Exception as e:
        logger.error(f"Error running permission audit: {str(e)}")
        messages.error(request, f'Error running permission audit: {str(e)}')

    return redirect('admin_permission_audit')

@login_required
@permission_required('auth.view_permission', raise_exception=True)
def download_report(request, filename):
    """Download a permission audit report."""
    # Get the output directory for permission review reports
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'permission_review')

    # Construct the full file path
    file_path = os.path.join(output_dir, filename)

    # Check if the file exists and is a CSV file
    if not os.path.exists(file_path) or not filename.endswith('.csv'):
        logger.error(f"Report file not found or invalid: {filename}")
        messages.error(request, 'Report file not found or invalid.')
        return redirect('admin_permission_audit')

    # Serve the file
    try:
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    except Exception as e:
        logger.error(f"Error serving report file {filename}: {str(e)}")
        messages.error(request, f'Error serving report file: {str(e)}')
        return redirect('admin_permission_audit')

@login_required
@permission_required('auth.view_permission', raise_exception=True)
def view_report(request, filename):
    """View a permission audit report."""
    # Get the output directory for permission review reports
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'permission_review')

    # Construct the full file path
    file_path = os.path.join(output_dir, filename)

    # Check if the file exists and is a CSV file
    if not os.path.exists(file_path) or not filename.endswith('.csv'):
        return JsonResponse({'error': 'Report file not found or invalid'}, status=404)

    # Serve the file content
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            return HttpResponse(content, content_type='text/csv')
    except Exception as e:
        logger.error(f"Error serving report file {filename}: {str(e)}")
        return JsonResponse({'error': f'Error serving report file: {str(e)}'}, status=500)

@login_required
@permission_required('auth.view_permission', raise_exception=True)
def get_objects_for_content_type(request):
    """Get objects for a specific content type."""
    content_type_id = request.GET.get('content_type_id')
    search_term = request.GET.get('search', '')

    if not content_type_id:
        return JsonResponse({'error': 'Content type ID is required'}, status=400)

    try:
        content_type = ContentType.objects.get(id=content_type_id)
        model = apps.get_model(content_type.app_label, content_type.model)

        # Get objects of this model
        objects = model.objects.all()

        # Apply search filter if provided
        if search_term:
            # Try to find common fields to search in
            searchable_fields = []
            for field in model._meta.fields:
                if field.get_internal_type() in ['CharField', 'TextField']:
                    searchable_fields.append(field.name)

            # If we have searchable fields, filter objects
            if searchable_fields:
                q_objects = Q()
                for field in searchable_fields:
                    q_objects |= Q(**{f"{field}__icontains": search_term})
                objects = objects.filter(q_objects)

        # Limit to a reasonable number
        objects = objects[:100]

        # Prepare the response
        result = []
        for obj in objects:
            # Try to get a meaningful representation of the object
            display_name = str(obj)
            result.append({
                'id': obj.id,
                'text': display_name
            })

        return JsonResponse({'objects': result})
    except ContentType.DoesNotExist:
        return JsonResponse({'error': 'Content type not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting objects for content type {content_type_id}: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
