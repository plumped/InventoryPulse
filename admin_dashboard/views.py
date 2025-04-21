import logging
import sys

import django
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group, Permission
from django.db import connections
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from accessmanagement.models import WarehouseAccess
from core.utils.filters import filter_users, filter_departments, filter_taxes, filter_interface_types, \
    filter_supplier_interfaces, filter_company_addresses
from core.utils.forms import handle_form_view
from core.utils.logging_utils import log_list_view_usage
from core.utils.pagination import paginate_queryset
from documents.models import StandardField, Document, DocumentType, DocumentTemplate
from interfaces.models import InterfaceType
from inventory.models import Warehouse
from master_data.forms.addresses_forms import CompanyAddressForm
from master_data.forms.systemsettings_forms import SystemSettingsForm
from master_data.forms.tax_forms import TaxForm
from master_data.forms.workflows_forms import WorkflowSettingsForm
from master_data.models.addresses_models import CompanyAddress, CompanyAddressType
from master_data.models.organisations_models import Department
from master_data.models.systemsettings_models import WorkflowSettings, SystemSettings
from master_data.models.tax_models import Tax
from .forms import UserCreateForm, UserEditForm, GroupForm, DepartmentForm, InterfaceTypeForm, DocumentTypeForm

logger = logging.getLogger(__name__)

# --- Hook-Funktionen ---
def post_save_user_create(user, cleaned_data):
    password = cleaned_data.get('password')
    if password:
        user.set_password(password)
        user.save()
    user.groups.set(cleaned_data.get('groups', []))
    try:
        for dept in cleaned_data.get('departments', []):
            user.profile.departments.add(dept)
        user.profile.save()
    except AttributeError:
        logger.warning(f"Profile missing for user {user.username} during creation.")

    logger.info(f"User {user.username} created and assigned groups/departments.")

def post_save_user_edit(user, cleaned_data):
    if cleaned_data.get('password'):
        user.set_password(cleaned_data['password'])
        user.save()
    user.groups.set(cleaned_data.get('groups', []))
    try:
        user.profile.departments.clear()
        for dept in cleaned_data.get('departments', []):
            user.profile.departments.add(dept)
        user.profile.save()
    except AttributeError:
        logger.warning(f"Profile missing for user {user.username} during edit.")

    logger.info(f"User {user.username} updated.")

def post_save_group(group, cleaned_data):
    try:
        permission_ids = cleaned_data.get('permissions', [])

        # Filtern nach existierenden Berechtigungen
        existing_permissions = Permission.objects.filter(id__in=permission_ids)

        # Nur die existierenden Berechtigungen setzen
        group.permissions.set(existing_permissions)

        logger.info(f"Group {group.name} permissions updated with {existing_permissions.count()} permissions.")
        return True
    except Exception as e:
        logger.error(f"Error updating permissions for group {group.name}: {str(e)}")
        # Fehler ausgeben, um bei der Fehlersuche zu helfen
        logger.error(f"Permission IDs: {permission_ids}")
        return False



def post_save_department(dept, cleaned_data):
    manager = cleaned_data.get('manager')
    if manager:
        dept.manager = manager
        dept.save()
    members = cleaned_data.get('members', [])
    dept.user_profiles.clear()
    for user in members:
        try:
            dept.user_profiles.add(user.profile)
        except Exception as e:
            logger.warning(f"Could not add profile for user {user} to department {dept.name}: {e}")

    logger.info(f"Department {dept.name} updated with new manager and members.")


@login_required
@permission_required('admin_dashboard.view_admin_dashboard', raise_exception=True)
def admin_dashboard(request):
    """Main admin dashboard view."""
    logger.info(f"Dashboard accessed by {request.user}.")

    stats = {
        'users_count': User.objects.count(),
        'groups_count': Group.objects.count(),
        'departments_count': Department.objects.count(),
        'warehouses_count': Warehouse.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'admin_users': User.objects.filter(
            Q(is_superuser=True) | Q(user_permissions__codename='access_admin')).distinct().count(),
    }

    # Add permission-related statistics
    try:
        from accessmanagement.models import WarehouseAccess, ObjectPermission, RoleHierarchy
        permission_stats = {
            'warehouse_access_count': WarehouseAccess.objects.count(),
            'object_permission_count': ObjectPermission.objects.count(),
            'role_hierarchy_count': RoleHierarchy.objects.count(),
            'time_based_permission_count': ObjectPermission.objects.filter(
                Q(valid_from__isnull=False) | Q(valid_until__isnull=False)
            ).count(),
        }
        stats.update(permission_stats)
    except Exception as e:
        logger.warning(f"Permission stats loading failed: {e}")

    try:
        from interfaces.models import SupplierInterface
        interface_stats = {
            'total': SupplierInterface.objects.count(),
            'active': SupplierInterface.objects.filter(is_active=True).count(),
        }
    except Exception as e:
        interface_stats = None
        logger.warning(f"Interface stats loading failed: {e}")

    try:
        from django.contrib.admin.models import LogEntry
        recent_activities = LogEntry.objects.all().order_by('-action_time')[:10]
    except Exception as e:
        recent_activities = []
        logger.warning(f"Loading recent admin log entries failed: {e}")

    workflow_settings, _ = WorkflowSettings.objects.get_or_create(pk=1)

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    django_version = django.get_version()
    database_type = request.META.get('DATABASE_ENGINE', connections.databases['default']['ENGINE'].split('.')[-1])

    context = {
        'stats': stats,
        'recent_activities': recent_activities,
        'workflow_settings': workflow_settings,
        'python_version': python_version,
        'django_version': django_version,
        'database_type': database_type,
        'section': 'dashboard',
        'interface_stats': interface_stats,
    }

    return render(request, 'admin_dashboard/dashboard.html', context)



@login_required
@permission_required('auth.view_user', raise_exception=True)
def user_management(request):
    filters = {
        'search': request.GET.get('search', ''),
        'status': request.GET.get('status', ''),
        'group': request.GET.get('group', ''),
    }
    sort_by = request.GET.get('sort', 'username')
    page = request.GET.get('page')

    log_list_view_usage(
        request,
        view_name="user_management",
        filters=filters,
        sort_by=sort_by,
        page=page
    )

    users = User.objects.all()
    users = filter_users(users, filters).order_by(sort_by)
    users_page = paginate_queryset(users, page, per_page=20)

    context = {
        'users': users_page,
        'search_query': filters['search'],
        'status_filter': filters['status'],
        'group_filter': filters['group'],
        'groups': Group.objects.all(),
        'sort_by': sort_by,
        'section': 'users'
    }

    return render(request, 'admin_dashboard/user_management.html', context)



@login_required
@permission_required('auth.add_user', raise_exception=True)
def user_create(request):
    return handle_form_view(
        request,
        form_class=UserCreateForm,
        success_message='Benutzer wurde erfolgreich erstellt.',
        redirect_url='admin_user_management',
        template='admin_dashboard/user_create.html',
        context_extra={
            'groups': Group.objects.all(),
            'departments': Department.objects.all(),
            'section': 'users'
        },
        post_save_hook=post_save_user_create
    )

@login_required
@permission_required('auth.change_user', raise_exception=True)
def user_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    try:
        departments = Department.objects.all()
        user_departments = user.profile.departments.all()
    except:
        departments = []
        user_departments = []

    return handle_form_view(
        request,
        form_class=UserEditForm,
        instance=user,
        success_message=f'Benutzer "{user.username}" wurde erfolgreich aktualisiert.',
        redirect_url='admin_user_management',
        template='admin_dashboard/user_edit.html',
        context_extra={
            'user_obj': user,
            'groups': Group.objects.all(),
            'user_groups': user.groups.all(),
            'departments': departments,
            'user_departments': user_departments,
            'section': 'users'
        },
        post_save_hook=post_save_user_edit
    )


@login_required
@permission_required('auth.delete_user', raise_exception=True)
def user_delete(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        username = user.username
        user.delete()
        logger.info(f"User {username} deleted by {request.user}.")
        messages.success(request, f'Benutzer "{username}" wurde erfolgreich gelöscht.')
        return redirect('admin_user_management')

    context = {'user_obj': user, 'section': 'users'}
    return render(request, 'admin_dashboard/user_confirm_delete.html', context)


@login_required
@permission_required('auth.view_group', raise_exception=True)
def group_management(request):
    log_list_view_usage(request, view_name="group_management")
    groups = Group.objects.annotate(user_count=Count('user'))

    context = {
        'groups': groups,
        'section': 'groups'
    }

    return render(request, 'admin_dashboard/group_management.html', context)


@login_required
@staff_member_required
def group_create(request):
    # Standard Django permission actions
    standard_actions = ['view', 'add', 'change', 'delete']

    # Get all permissions and organize them by app/model
    permissions_by_app = {}
    all_permissions = Permission.objects.all().order_by('content_type__app_label', 'codename')

    for permission in all_permissions:
        app_label = permission.content_type.app_label
        model_name = permission.content_type.model

        # Skip contenttype and auth app permissions if you don't want to expose them
        if app_label in ['contenttypes', 'sessions']:
            continue

        if app_label not in permissions_by_app:
            permissions_by_app[app_label] = {}

        if model_name not in permissions_by_app[app_label]:
            permissions_by_app[app_label][model_name] = []

        permissions_by_app[app_label][model_name].append(permission)

    return handle_form_view(
        request,
        form_class=GroupForm,
        success_message='Gruppe wurde erfolgreich erstellt.',
        redirect_url='admin_group_management',
        template='admin_dashboard/group_create.html',
        context_extra={
            'permissions_by_app': permissions_by_app,
            'standard_actions': standard_actions,
            'section': 'groups'
        },
        post_save_hook=post_save_group
    )


@login_required
@staff_member_required
def group_edit(request, group_id):
    group = get_object_or_404(Group, pk=group_id)

    # Standard Django permission actions
    standard_actions = ['view', 'add', 'change', 'delete']

    # Get all permissions and organize them by app/model
    permissions_by_app = {}
    all_permissions = Permission.objects.all().order_by('content_type__app_label', 'codename')

    for permission in all_permissions:
        app_label = permission.content_type.app_label
        model_name = permission.content_type.model

        # Skip contenttype and auth app permissions if you don't want to expose them
        if app_label in ['contenttypes', 'sessions']:
            continue

        if app_label not in permissions_by_app:
            permissions_by_app[app_label] = {}

        if model_name not in permissions_by_app[app_label]:
            permissions_by_app[app_label][model_name] = []

        permissions_by_app[app_label][model_name].append(permission)

    return handle_form_view(
        request,
        form_class=GroupForm,
        instance=group,
        success_message=f'Gruppe "{group.name}" wurde erfolgreich aktualisiert.',
        redirect_url='admin_group_management',
        template='admin_dashboard/group_edit.html',
        context_extra={
            'group': group,
            'permissions_by_app': permissions_by_app,
            'standard_actions': standard_actions,
            'group_permissions': group.permissions.all(),
            'section': 'groups'
        },
        post_save_hook=post_save_group
    )



@login_required
@staff_member_required
def group_delete(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if request.method == 'POST':
        group_name = group.name
        group.delete()
        logger.info(f"Group {group_name} deleted by {request.user}.")
        messages.success(request, f'Gruppe "{group_name}" wurde erfolgreich gelöscht.')
        return redirect('admin_group_management')

    user_count = User.objects.filter(groups=group).count()
    context = {'group': group, 'user_count': user_count, 'section': 'groups'}
    return render(request, 'admin_dashboard/group_confirm_delete.html', context)


@login_required
@staff_member_required
def department_management(request):
    filters = {
        'search': request.GET.get('search', '')
    }

    log_list_view_usage(request, view_name="department_management", filters=filters)

    departments = Department.objects.all()
    departments = filter_departments(departments, filters)

    departments_with_counts = []
    for dept in departments:
        user_count = dept.user_profiles.count()
        departments_with_counts.append({
            'department': dept,
            'user_count': user_count
        })

    context = {
        'departments': departments_with_counts,
        'section': 'departments',
        'search_query': filters['search']
    }

    return render(request, 'admin_dashboard/department_management.html', context)


@login_required
@staff_member_required
def department_create(request):
    return handle_form_view(
        request,
        form_class=DepartmentForm,
        success_message='Abteilung wurde erfolgreich erstellt.',
        redirect_url='admin_department_management',
        template='admin_dashboard/department_create.html',
        context_extra={
            'users': User.objects.all(),
            'section': 'departments'
        },
        post_save_hook=post_save_department
    )


@login_required
@staff_member_required
def department_edit(request, department_id):
    department = get_object_or_404(Department, pk=department_id)
    initial_members = [profile.user.id for profile in department.user_profiles.all()]
    return handle_form_view(
        request,
        form_class=DepartmentForm,
        instance=department,
        success_message=f'Abteilung "{department.name}" wurde erfolgreich aktualisiert.',
        redirect_url='admin_department_management',
        template='admin_dashboard/department_edit.html',
        context_extra={
            'department': department,
            'users': User.objects.all(),
            'department_members': [profile.user for profile in department.user_profiles.all()],
            'section': 'departments'
        },
        post_save_hook=post_save_department
    )


@login_required
@staff_member_required
def department_delete(request, department_id):
    department = get_object_or_404(Department, pk=department_id)
    if request.method == 'POST':
        department_name = department.name
        department.delete()
        logger.info(f"Department {department_name} deleted by {request.user}.")
        messages.success(request, f'Abteilung "{department_name}" wurde erfolgreich gelöscht.')
        return redirect('admin_department_management')

    member_count = department.user_profiles.count()
    warehouse_access_count = WarehouseAccess.objects.filter(department=department).count()
    context = {
        'department': department,
        'member_count': member_count,
        'warehouse_access_count': warehouse_access_count,
        'section': 'departments'
    }
    return render(request, 'admin_dashboard/department_confirm_delete.html', context)


@login_required
@staff_member_required
def warehouse_access_delete(request, access_id):
    access = get_object_or_404(WarehouseAccess, pk=access_id)
    if request.method == 'POST':
        access.delete()
        logger.info(f"WarehouseAccess ID {access_id} deleted by {request.user}.")
        messages.success(request, f'Lagerzugriff wurde erfolgreich gelöscht.')
        return redirect('warehouse_access_management')

    context = {'access': access, 'section': 'warehouse_access'}
    return render(request, 'admin_dashboard/warehouse_access_confirm_delete.html', context)


@login_required
@staff_member_required
def system_settings(request):
    settings, _ = SystemSettings.objects.get_or_create(pk=1)
    return handle_form_view(
        request,
        form_class=SystemSettingsForm,
        instance=settings,
        success_message='Systemeinstellungen wurden erfolgreich aktualisiert.',
        redirect_url='admin_system_settings',
        template='admin_dashboard/system_settings.html',
        context_extra={'section': 'system_settings'}
    )


@login_required
@staff_member_required
def workflow_settings(request):
    settings, _ = WorkflowSettings.objects.get_or_create(pk=1)
    return handle_form_view(
        request,
        form_class=WorkflowSettingsForm,
        instance=settings,
        success_message='Workflow-Einstellungen wurden erfolgreich aktualisiert.',
        redirect_url='admin_workflow_settings',
        template='admin_dashboard/workflow_settings.html',
        context_extra={'section': 'workflow_settings'}
    )



# AJAX-Endpunkte

@login_required
@staff_member_required
def get_user_details(request, user_id):
    """AJAX endpoint to get user details."""
    user = get_object_or_404(User, pk=user_id)
    logger.debug(f"AJAX: get_user_details called by {request.user} for user ID {user_id}")

    data = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'groups': list(user.groups.values('id', 'name')),
        'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
        'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
    }

    try:
        data['departments'] = list(user.profile.departments.values('id', 'name'))
    except Exception as e:
        data['departments'] = []
        logger.warning(f"Could not fetch departments for user {user.username}: {e}")

    return JsonResponse(data)



@login_required
@staff_member_required
def get_department_details(request, department_id):
    """AJAX endpoint to get department details."""
    department = get_object_or_404(Department, pk=department_id)
    logger.debug(f"AJAX: get_department_details called by {request.user} for department ID {department_id}")

    data = {
        'id': department.id,
        'name': department.name,
        'code': department.code,
        'manager': {
            'id': department.manager.id,
            'username': department.manager.username,
            'name': f"{department.manager.first_name} {department.manager.last_name}".strip()
        } if department.manager else None,
        'members': []
    }

    try:
        for profile in department.user_profiles.all():
            data['members'].append({
                'id': profile.user.id,
                'username': profile.user.username,
                'name': f"{profile.user.first_name} {profile.user.last_name}".strip() or profile.user.username
            })
    except Exception as e:
        logger.warning(f"Could not fetch members for department {department.name}: {e}")

    return JsonResponse(data)



@login_required
@staff_member_required
def tax_management(request):
    filters = {
        'search': request.GET.get('search', '')
    }

    log_list_view_usage(request, view_name="tax_management", filters=filters)

    taxes = Tax.objects.all()
    taxes = filter_taxes(taxes, filters).order_by('rate')

    context = {
        'taxes': taxes,
        'section': 'taxes',
        'search_query': filters['search']
    }

    return render(request, 'admin_dashboard/tax_management.html', context)


@login_required
@staff_member_required
def tax_create(request):
    return handle_form_view(
        request,
        form_class=TaxForm,
        success_message='Mehrwertsteuersatz wurde erfolgreich erstellt.',
        redirect_url='admin_tax_management',
        template='admin_dashboard/tax_form.html',
        context_extra={'section': 'taxes'}
    )


@login_required
@staff_member_required
def tax_edit(request, tax_id):
    tax = get_object_or_404(Tax, pk=tax_id)
    return handle_form_view(
        request,
        form_class=TaxForm,
        instance=tax,
        success_message=f'Mehrwertsteuersatz "{tax.name}" wurde erfolgreich aktualisiert.',
        redirect_url='admin_tax_management',
        template='admin_dashboard/tax_form.html',
        context_extra={'section': 'taxes', 'tax': tax}
    )


@login_required
@staff_member_required
def tax_delete(request, tax_id):
    """Einen Mehrwertsteuersatz löschen."""
    tax = get_object_or_404(Tax, pk=tax_id)

    # Überprüfen, ob der Steuersatz bei Produkten verwendet wird
    products_with_tax = tax.product_set.count()

    if request.method == 'POST':
        tax_name = tax.name
        tax.delete()
        messages.success(request, f'Mehrwertsteuersatz "{tax_name}" wurde erfolgreich gelöscht.')
        return redirect('admin_tax_management')

    context = {
        'tax': tax,
        'products_with_tax': products_with_tax,
        'section': 'taxes'
    }

    return render(request, 'admin_dashboard/tax_confirm_delete.html', context)

@login_required
@staff_member_required
def interface_management(request):
    from interfaces.models import InterfaceType, SupplierInterface, InterfaceLog
    from django.utils import timezone

    filters = {
        'search': request.GET.get('search', ''),
        'type': request.GET.get('type', ''),
        'status': request.GET.get('status', '')
    }

    log_list_view_usage(request, view_name="interface_management", filters=filters)

    interface_types = InterfaceType.objects.all().order_by('name')
    interfaces = SupplierInterface.objects.all()
    interfaces = filter_supplier_interfaces(interfaces, filters)

    for interface_type in interface_types:
        interface_type.count = interfaces.filter(interface_type=interface_type).count()

    total_interfaces = interfaces.count()
    active_interfaces = interfaces.filter(is_active=True).count()

    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    success_count = InterfaceLog.objects.filter(status='success', timestamp__gte=thirty_days_ago).count()
    failed_count = InterfaceLog.objects.filter(status='failed', timestamp__gte=thirty_days_ago).count()
    total_transmissions = success_count + failed_count
    success_rate = (success_count / total_transmissions * 100) if total_transmissions > 0 else 0

    context = {
        'interface_types': interface_types,
        'total_interfaces': total_interfaces,
        'active_interfaces': active_interfaces,
        'success_count': success_count,
        'failed_count': failed_count,
        'total_transmissions': total_transmissions,
        'success_rate': success_rate,
        'filters': filters,
        'section': 'interfaces'
    }

    return render(request, 'admin_dashboard/interface_management.html', context)


@login_required
@staff_member_required
def interface_type_management(request):
    from interfaces.models import InterfaceType, SupplierInterface

    filters = {
        'search': request.GET.get('search', '')
    }

    log_list_view_usage(request, view_name="interface_type_management", filters=filters)

    interface_types = InterfaceType.objects.all()
    interface_types = filter_interface_types(interface_types, filters).order_by('name')

    for interface_type in interface_types:
        interface_type.count = SupplierInterface.objects.filter(interface_type=interface_type).count()

    context = {
        'interface_types': interface_types,
        'search_query': filters['search'],
        'section': 'interfaces'
    }

    return render(request, 'admin_dashboard/interface_type_management.html', context)


@login_required
@staff_member_required
def interface_type_create(request):
    return handle_form_view(
        request,
        form_class=InterfaceTypeForm,
        success_message='Schnittstellentyp wurde erfolgreich erstellt.',
        redirect_url='admin_interface_type_management',
        template='admin_dashboard/interface_type_form.html',
        context_extra={
            'section': 'interfaces',
            'title': 'Neuen Schnittstellentyp erstellen'
        }
    )


@login_required
@staff_member_required
def interface_type_edit(request, type_id):
    interface_type = get_object_or_404(InterfaceType, pk=type_id)
    return handle_form_view(
        request,
        form_class=InterfaceTypeForm,
        instance=interface_type,
        success_message=f'Schnittstellentyp "{interface_type.name}" wurde erfolgreich aktualisiert.',
        redirect_url='admin_interface_type_management',
        template='admin_dashboard/interface_type_form.html',
        context_extra={
            'section': 'interfaces',
            'interface_type': interface_type,
            'title': f'Schnittstellentyp "{interface_type.name}" bearbeiten'
        }
    )


@login_required
@staff_member_required
def interface_type_delete(request, type_id):
    """Schnittstellentyp löschen."""
    from interfaces.models import InterfaceType, SupplierInterface

    interface_type = get_object_or_404(InterfaceType, pk=type_id)

    # Prüfen, ob dieser Typ von Schnittstellen verwendet wird
    interfaces_using_type = SupplierInterface.objects.filter(interface_type=interface_type).count()

    if request.method == 'POST':
        if interfaces_using_type > 0:
            messages.error(
                request,
                f'Schnittstellentyp "{interface_type.name}" kann nicht gelöscht werden, da er von {interfaces_using_type} Schnittstellen verwendet wird.'
            )
        else:
            type_name = interface_type.name
            interface_type.delete()
            messages.success(request, f'Schnittstellentyp "{type_name}" wurde erfolgreich gelöscht.')

        return redirect('admin_interface_type_management')

    context = {
        'interface_type': interface_type,
        'interfaces_using_type': interfaces_using_type,
        'section': 'interfaces'
    }

    return render(request, 'admin_dashboard/interface_type_confirm_delete.html', context)


@login_required
@staff_member_required
def admin_menu(request):
    """Admin menu view with links to all admin sections."""
    return render(request, 'admin_dashboard/base_menu.html', {'section': 'menu'})


@login_required
@staff_member_required
def company_address_management(request):
    filters = {
        'search': request.GET.get('search', ''),
        'type': request.GET.get('type', ''),
        'is_default': request.GET.get('is_default', '')
    }

    log_list_view_usage(request, view_name="company_address_management", filters=filters)

    addresses_by_type = []
    for address_type, address_type_display in CompanyAddressType.choices:
        qs = CompanyAddress.objects.filter(address_type=address_type)
        filtered_addresses = filter_company_addresses(qs, filters)
        if filtered_addresses.exists() or address_type in ['headquarters', 'billing']:
            addresses_by_type.append({
                'type': address_type,
                'display': address_type_display,
                'addresses': filtered_addresses,
                'has_default': filtered_addresses.filter(is_default=True).exists()
            })

    context = {
        'addresses_by_type': addresses_by_type,
        'filters': filters,
        'section': 'company_addresses'
    }

    return render(request, 'admin_dashboard/company_address_management.html', context)


@login_required
@staff_member_required
def company_address_create(request):
    initial = {}
    address_type = request.GET.get('type')
    if address_type and address_type in dict(CompanyAddressType.choices):
        initial['address_type'] = address_type

    return handle_form_view(
        request,
        form_class=CompanyAddressForm,
        success_message='Unternehmensadresse wurde erfolgreich erstellt.',
        redirect_url='admin_company_address_management',
        template='admin_dashboard/company_address_form.html',
        context_extra={'section': 'company_addresses'},
        instance=None
    )


@login_required
@staff_member_required
def company_address_edit(request, address_id):
    address = get_object_or_404(CompanyAddress, pk=address_id)
    return handle_form_view(
        request,
        form_class=CompanyAddressForm,
        instance=address,
        success_message=f'Adresse "{address.name}" wurde erfolgreich aktualisiert.',
        redirect_url='admin_company_address_management',
        template='admin_dashboard/company_address_form.html',
        context_extra={'section': 'company_addresses', 'address': address}
    )


@login_required
@staff_member_required
def company_address_delete(request, address_id):
    """Unternehmensadresse löschen."""
    address = get_object_or_404(CompanyAddress, pk=address_id)

    if request.method == 'POST':
        address_name = address.name
        address_type_display = address.get_address_type_display()
        address.delete()
        messages.success(request, f'Adresse "{address_name}" ({address_type_display}) wurde erfolgreich gelöscht.')
        return redirect('admin_company_address_management')

    context = {
        'address': address,
        'section': 'company_addresses'
    }

    return render(request, 'admin_dashboard/company_address_confirm_delete.html', context)


@login_required
@staff_member_required
def document_type_management(request):
    """View for managing document types."""
    filters = {
        'search': request.GET.get('search', '')
    }

    log_list_view_usage(request, view_name="document_type_management", filters=filters)

    # Get all document types with document count
    document_types = DocumentType.objects.all().annotate(document_count=Count('documents'))

    # Apply search filter if provided
    if filters['search']:
        document_types = document_types.filter(
            name__icontains=filters['search']
        ) | document_types.filter(
            code__icontains=filters['search']
        )

    context = {
        'document_types': document_types,
        'search_query': filters['search'],
        'section': 'document_types'
    }

    return render(request, 'admin_dashboard/document_type_management.html', context)


@login_required
@staff_member_required
def document_type_create(request):
    """View for creating a new document type."""
    return handle_form_view(
        request,
        form_class=DocumentTypeForm,
        success_message='Dokumenttyp wurde erfolgreich erstellt.',
        redirect_url='admin_document_type_management',
        template='admin_dashboard/document_type_form.html',
        context_extra={'section': 'document_types'}
    )


@login_required
@staff_member_required
def document_type_edit(request, type_id):
    """View for editing an existing document type."""
    document_type = get_object_or_404(DocumentType, pk=type_id)
    return handle_form_view(
        request,
        form_class=DocumentTypeForm,
        instance=document_type,
        success_message=f'Dokumenttyp "{document_type.name}" wurde erfolgreich aktualisiert.',
        redirect_url='admin_document_type_management',
        template='admin_dashboard/document_type_form.html',
        context_extra={'section': 'document_types', 'document_type': document_type}
    )


@login_required
@staff_member_required
def document_type_delete(request, type_id):
    """View for deleting a document type."""
    document_type = get_object_or_404(DocumentType, pk=type_id)

    # Check for associated documents and templates
    documents_count = Document.objects.filter(document_type=document_type).count()
    templates_count = DocumentTemplate.objects.filter(document_type=document_type).count()
    standard_fields_count = StandardField.objects.filter(document_type=document_type).count()

    if request.method == 'POST':
        type_name = document_type.name
        document_type.delete()
        messages.success(request, f'Dokumenttyp "{type_name}" wurde erfolgreich gelöscht.')
        return redirect('admin_document_type_management')

    context = {
        'document_type': document_type,
        'documents_count': documents_count,
        'templates_count': templates_count,
        'standard_fields_count': standard_fields_count,
        'section': 'document_types'
    }

    return render(request, 'admin_dashboard/document_type_confirm_delete.html', context)


@login_required
@staff_member_required
def setup_standard_fields(request):
    """View for setting up standard fields for document types."""
    from django.core.management import call_command
    from io import StringIO
    import sys
    from documents.models import StandardField, TemplateField

    if request.method == 'POST':
        # Execute management command
        reset = 'reset' in request.POST

        # Capture command output
        output = StringIO()
        old_stdout, sys.stdout = sys.stdout, output

        try:
            # Get count before execution
            before_count = StandardField.objects.count()

            # Execute command
            call_command('setup_standard_fields', reset=reset)

            # Get count after execution
            after_count = StandardField.objects.count()

            # Calculate difference
            created_count = after_count - before_count

            # Restore stdout
            sys.stdout = old_stdout

            # Get command output
            command_output = output.getvalue()

            if reset:
                messages.success(
                    request,
                    f'Standardfelder wurden zurückgesetzt und neu angelegt. '
                    f'{after_count} Felder sind jetzt vorhanden.'
                )
            else:
                if created_count > 0:
                    messages.success(
                        request,
                        f'{created_count} neue Standardfelder wurden erstellt. '
                        f'Insgesamt sind jetzt {after_count} Felder vorhanden.'
                    )
                else:
                    messages.info(
                        request,
                        'Es wurden keine neuen Standardfelder erstellt, da alle bereits existieren. '
                        f'Insgesamt sind {after_count} Felder vorhanden.'
                    )

            # Log details for debugging
            logger.info(f"Standard fields setup: before={before_count}, after={after_count}, created={created_count}")
            logger.debug(f"Command output: {command_output}")

        except Exception as e:
            # Restore stdout
            sys.stdout = old_stdout

            logger.error(f"Error setting up standard fields: {e}")
            messages.error(request, f'Fehler beim Einrichten der Standardfelder: {str(e)}')

        return redirect('admin_document_type_management')

    # Get all document types
    document_types = DocumentType.objects.all()

    # Count existing fields and organize them by document type
    fields_by_type = {}
    total_fields_count = 0

    for doc_type in document_types:
        fields = StandardField.objects.filter(document_type=doc_type).order_by('order', 'name')
        fields_by_type[doc_type.id] = {
            'doc_type': doc_type,
            'fields': fields,
            'count': fields.count(),
        }
        total_fields_count += fields.count()

    # Get list of document types with no fields
    types_without_fields = [
        doc_type for doc_type in document_types
        if fields_by_type[doc_type.id]['count'] == 0
    ]

    # Explicitly create dictionaries from TemplateField choices
    field_type_labels = dict(TemplateField.FIELD_TYPES)
    extraction_method_labels = dict(TemplateField.EXTRACTION_METHODS)

    context = {
        'existing_fields': total_fields_count,
        'fields_by_type': fields_by_type,
        'document_types': document_types,
        'types_without_fields': types_without_fields,
        'section': 'document_types',
        'field_type_labels': field_type_labels,
        'extraction_method_labels': extraction_method_labels,
    }

    return render(request, 'admin_dashboard/setup_standard_fields.html', context)
