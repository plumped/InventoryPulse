# admin_dashboard/views.py
from django.db import connections
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group, Permission
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.utils import timezone
import sys
import django

from core.permissions import PERMISSION_AREAS, PERMISSION_LEVELS, get_permission_name
from inventory.models import Department, Warehouse, WarehouseAccess
from core.decorators import permission_required

from .forms import SystemSettingsForm, WorkflowSettingsForm, UserCreateForm, UserEditForm, GroupForm, DepartmentForm, \
    WarehouseAccessForm


# Hilfsfunktion zur Prüfung von Admin-Berechtigungen
def is_admin(user):
    """Check if user has admin privileges."""
    return user.is_superuser or user.has_perm('admin_dashboard.access_admin')


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Main admin dashboard view."""
    # Statistiken sammeln
    stats = {
        'users_count': User.objects.count(),
        'groups_count': Group.objects.count(),
        'departments_count': Department.objects.count(),
        'warehouses_count': Warehouse.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'admin_users': User.objects.filter(
            Q(is_superuser=True) | Q(user_permissions__codename='access_admin')).distinct().count(),
    }

    # Letzte Benutzeraktivitäten (falls vorhanden)
    try:
        from django.contrib.admin.models import LogEntry
        recent_activities = LogEntry.objects.all().order_by('-action_time')[:10]
    except:
        recent_activities = []

    # Workflow-Einstellungen für die Visualisierung
    from .models import WorkflowSettings
    workflow_settings, _ = WorkflowSettings.objects.get_or_create(pk=1)

    # System-Informationen
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
        'section': 'dashboard'
    }

    return render(request, 'admin_dashboard/dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def user_management(request):
    """User management view."""
    # Filter und Suche
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    group_filter = request.GET.get('group', '')

    users = User.objects.all()

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    if status_filter:
        is_active = status_filter == 'active'
        users = users.filter(is_active=is_active)

    if group_filter:
        users = users.filter(groups__id=group_filter)

    # Sortierung
    sort_by = request.GET.get('sort', 'username')
    if sort_by.startswith('-'):
        order_by = sort_by
    else:
        order_by = sort_by

    users = users.order_by(order_by)

    # Pagination
    paginator = Paginator(users, 20)
    page = request.GET.get('page')
    try:
        users_page = paginator.page(page)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)

    # Gruppen für Filter
    groups = Group.objects.all()

    context = {
        'users': users_page,
        'search_query': search_query,
        'status_filter': status_filter,
        'group_filter': group_filter,
        'groups': groups,
        'sort_by': sort_by,
        'section': 'users'
    }

    return render(request, 'admin_dashboard/user_management.html', context)


@login_required
@user_passes_test(is_admin)
def user_create(request):
    """Create a new user."""
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Passwort setzen
            user.set_password(form.cleaned_data['password'])
            user.save()

            # Gruppen zuweisen
            for group in form.cleaned_data['groups']:
                user.groups.add(group)

            # Abteilungen zuweisen
            try:
                for dept in form.cleaned_data['departments']:
                    user.profile.departments.add(dept)
                user.profile.save()
            except:
                pass

            messages.success(request, f'Benutzer "{user.username}" wurde erfolgreich erstellt.')
            return redirect('admin_user_management')
    else:
        form = UserCreateForm()

    context = {
        'form': form,
        'groups': Group.objects.all(),
        'departments': Department.objects.all(),
        'section': 'users'
    }

    return render(request, 'admin_dashboard/user_create.html', context)


@login_required
@user_passes_test(is_admin)
def user_edit(request, user_id):
    """Edit a user."""
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save()

            # Passwort aktualisieren wenn angegeben
            if form.cleaned_data['password']:
                user.set_password(form.cleaned_data['password'])
                user.save()

            # Gruppen aktualisieren
            user.groups.clear()
            for group in form.cleaned_data['groups']:
                user.groups.add(group)

            # Abteilungen aktualisieren
            try:
                user.profile.departments.clear()
                for dept in form.cleaned_data['departments']:
                    user.profile.departments.add(dept)
                user.profile.save()
            except:
                pass

            messages.success(request, f'Benutzer "{user.username}" wurde erfolgreich aktualisiert.')
            return redirect('admin_user_management')
    else:
        form = UserEditForm(instance=user)

    # Gruppen und Abteilungen für die Auswahl
    try:
        # Abteilungen abrufen, falls verfügbar
        departments = Department.objects.all()
        user_departments = user.profile.departments.all()
    except:
        departments = []
        user_departments = []

    context = {
        'form': form,
        'user_obj': user,
        'groups': Group.objects.all(),
        'user_groups': user.groups.all(),
        'departments': departments,
        'user_departments': user_departments,
        'section': 'users'
    }

    return render(request, 'admin_dashboard/user_edit.html', context)


@login_required
@user_passes_test(is_admin)
def user_delete(request, user_id):
    """Delete a user."""
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'Benutzer "{username}" wurde erfolgreich gelöscht.')
        return redirect('admin_user_management')

    context = {
        'user_obj': user,
        'section': 'users'
    }

    return render(request, 'admin_dashboard/user_confirm_delete.html', context)


@login_required
@user_passes_test(is_admin)
def group_management(request):
    """Group management view."""
    groups = Group.objects.annotate(user_count=Count('user'))

    context = {
        'groups': groups,
        'section': 'groups'
    }

    return render(request, 'admin_dashboard/group_management.html', context)


@login_required
@user_passes_test(is_admin)
def group_create(request):
    """Create a new group."""
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save()

            # Berechtigungen zuweisen
            selected_permissions = request.POST.getlist('permissions')
            for perm_id in selected_permissions:
                try:
                    perm = Permission.objects.get(pk=perm_id)
                    group.permissions.add(perm)
                except Permission.DoesNotExist:
                    pass

            messages.success(request, f'Gruppe "{group.name}" wurde erfolgreich erstellt.')
            return redirect('admin_group_management')
    else:
        form = GroupForm()

    # Berechtigungen für die Auswahl
    permissions_by_area = {}
    for area in PERMISSION_AREAS.keys():
        area_perms = Permission.objects.filter(codename__contains=f'_{area}').order_by('codename')
        permissions_by_area[area] = area_perms

    context = {
        'form': form,
        'permissions_by_area': permissions_by_area,
        'permission_areas': PERMISSION_AREAS,
        'section': 'groups'
    }

    return render(request, 'admin_dashboard/group_create.html', context)


@login_required
@user_passes_test(is_admin)
def group_edit(request, group_id):
    """Edit a group."""
    group = get_object_or_404(Group, pk=group_id)

    if request.method == 'POST':
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            group = form.save()

            # Berechtigungen aktualisieren
            selected_permissions = request.POST.getlist('permissions')
            group.permissions.clear()
            for perm_id in selected_permissions:
                try:
                    perm = Permission.objects.get(pk=perm_id)
                    group.permissions.add(perm)
                except Permission.DoesNotExist:
                    pass

            messages.success(request, f'Gruppe "{group.name}" wurde erfolgreich aktualisiert.')
            return redirect('admin_group_management')
    else:
        form = GroupForm(instance=group)

    # Berechtigungen für die Auswahl
    permissions_by_area = {}
    for area in PERMISSION_AREAS.keys():
        area_perms = Permission.objects.filter(codename__contains=f'_{area}').order_by('codename')
        permissions_by_area[area] = area_perms

    group_permissions = group.permissions.all()

    context = {
        'form': form,
        'group': group,
        'permissions_by_area': permissions_by_area,
        'permission_areas': PERMISSION_AREAS,
        'group_permissions': group_permissions,
        'section': 'groups'
    }

    return render(request, 'admin_dashboard/group_edit.html', context)


@login_required
@user_passes_test(is_admin)
def group_delete(request, group_id):
    """Delete a group."""
    group = get_object_or_404(Group, pk=group_id)

    if request.method == 'POST':
        group_name = group.name
        group.delete()
        messages.success(request, f'Gruppe "{group_name}" wurde erfolgreich gelöscht.')
        return redirect('admin_group_management')

    # Benutzer in dieser Gruppe zählen
    user_count = User.objects.filter(groups=group).count()

    context = {
        'group': group,
        'user_count': user_count,
        'section': 'groups'
    }

    return render(request, 'admin_dashboard/group_confirm_delete.html', context)


@login_required
@user_passes_test(is_admin)
def department_management(request):
    """Department management view."""
    departments = Department.objects.all()

    # Mitgliederanzahl für jede Abteilung
    departments_with_counts = []
    for dept in departments:
        user_count = dept.user_profiles.count()
        departments_with_counts.append({
            'department': dept,
            'user_count': user_count
        })

    context = {
        'departments': departments_with_counts,
        'section': 'departments'
    }

    return render(request, 'admin_dashboard/department_management.html', context)


@login_required
@user_passes_test(is_admin)
def department_create(request):
    """Create a new department."""
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()

            # Manager setzen
            manager = form.cleaned_data.get('manager')
            if manager:
                department.manager = manager
                department.save()

            # Mitglieder hinzufügen
            if form.cleaned_data.get('members'):
                for user in form.cleaned_data['members']:
                    try:
                        department.user_profiles.add(user.profile)
                    except:
                        pass

            messages.success(request, f'Abteilung "{department.name}" wurde erfolgreich erstellt.')
            return redirect('admin_department_management')
    else:
        form = DepartmentForm()

    context = {
        'form': form,
        'users': User.objects.all(),
        'section': 'departments'
    }

    return render(request, 'admin_dashboard/department_create.html', context)


@login_required
@user_passes_test(is_admin)
def department_edit(request, department_id):
    """Edit a department."""
    department = get_object_or_404(Department, pk=department_id)

    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            department = form.save()

            # Manager aktualisieren
            manager = form.cleaned_data.get('manager')
            department.manager = manager
            department.save()

            # Mitglieder aktualisieren
            if 'members' in form.cleaned_data:
                # Alle Mitglieder entfernen
                department.user_profiles.clear()

                # Neue Mitglieder hinzufügen
                for user in form.cleaned_data['members']:
                    try:
                        department.user_profiles.add(user.profile)
                    except:
                        pass

            messages.success(request, f'Abteilung "{department.name}" wurde erfolgreich aktualisiert.')
            return redirect('admin_department_management')
    else:
        # Bestehende Mitglieder für die Initialisierung
        initial_members = [profile.user.id for profile in department.user_profiles.all()]
        form = DepartmentForm(instance=department, initial={
            'members': initial_members,
            'manager': department.manager
        })

    # Aktuell zugewiesene Mitglieder
    department_members = [profile.user for profile in department.user_profiles.all()]

    context = {
        'form': form,
        'department': department,
        'users': User.objects.all(),
        'department_members': department_members,
        'section': 'departments'
    }

    return render(request, 'admin_dashboard/department_edit.html', context)


@login_required
@user_passes_test(is_admin)
def department_delete(request, department_id):
    """Delete a department."""
    department = get_object_or_404(Department, pk=department_id)

    if request.method == 'POST':
        department_name = department.name
        department.delete()
        messages.success(request, f'Abteilung "{department_name}" wurde erfolgreich gelöscht.')
        return redirect('admin_department_management')

    # Mitglieder in dieser Abteilung zählen
    member_count = department.user_profiles.count()

    # Prüfen, ob Warehouse-Zugriffe existieren
    warehouse_access_count = WarehouseAccess.objects.filter(department=department).count()

    context = {
        'department': department,
        'member_count': member_count,
        'warehouse_access_count': warehouse_access_count,
        'section': 'departments'
    }

    return render(request, 'admin_dashboard/department_confirm_delete.html', context)


@login_required
@user_passes_test(is_admin)
def warehouse_access_management(request):
    """Warehouse access management view."""
    accesses = WarehouseAccess.objects.select_related('warehouse', 'department').all()

    context = {
        'accesses': accesses,
        'warehouses': Warehouse.objects.filter(is_active=True),
        'departments': Department.objects.all(),
        'section': 'warehouse_access'
    }

    return render(request, 'admin_dashboard/warehouse_access_management.html', context)


@login_required
@user_passes_test(is_admin)
def warehouse_access_create(request):
    """Create a new warehouse access."""
    if request.method == 'POST':
        form = WarehouseAccessForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Lagerzugriff wurde erfolgreich erstellt.')
            return redirect('admin_warehouse_access_management')
    else:
        form = WarehouseAccessForm()

    context = {
        'form': form,
        'warehouses': Warehouse.objects.filter(is_active=True),
        'departments': Department.objects.all(),
        'section': 'warehouse_access'
    }

    return render(request, 'admin_dashboard/warehouse_access_form.html', context)


@login_required
@user_passes_test(is_admin)
def warehouse_access_edit(request, access_id):
    """Edit a warehouse access."""
    access = get_object_or_404(WarehouseAccess, pk=access_id)

    if request.method == 'POST':
        form = WarehouseAccessForm(request.POST, instance=access)
        if form.is_valid():
            form.save()
            messages.success(request, f'Lagerzugriff wurde erfolgreich aktualisiert.')
            return redirect('admin_warehouse_access_management')
    else:
        form = WarehouseAccessForm(instance=access)

    context = {
        'form': form,
        'access': access,
        'section': 'warehouse_access'
    }

    return render(request, 'admin_dashboard/warehouse_access_edit.html', context)


@login_required
@user_passes_test(is_admin)
def warehouse_access_delete(request, access_id):
    """Delete a warehouse access."""
    access = get_object_or_404(WarehouseAccess, pk=access_id)

    if request.method == 'POST':
        access.delete()
        messages.success(request, f'Lagerzugriff wurde erfolgreich gelöscht.')
        return redirect('admin_warehouse_access_management')

    context = {
        'access': access,
        'section': 'warehouse_access'
    }

    return render(request, 'admin_dashboard/warehouse_access_confirm_delete.html', context)


@login_required
@user_passes_test(is_admin)
def system_settings(request):
    """System settings view."""
    # Settings Model abrufen oder erstellen
    from .models import SystemSettings
    settings, created = SystemSettings.objects.get_or_create(pk=1)

    if request.method == 'POST':
        form = SystemSettingsForm(request.POST, request.FILES, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Systemeinstellungen wurden erfolgreich aktualisiert.')
            return redirect('admin_system_settings')
    else:
        form = SystemSettingsForm(instance=settings)

    context = {
        'form': form,
        'section': 'system_settings'
    }

    return render(request, 'admin_dashboard/system_settings.html', context)


@login_required
@user_passes_test(is_admin)
def workflow_settings(request):
    """Workflow settings view."""
    # WorkflowSettings Model abrufen oder erstellen
    from .models import WorkflowSettings
    settings, created = WorkflowSettings.objects.get_or_create(pk=1)

    if request.method == 'POST':
        form = WorkflowSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Workflow-Einstellungen wurden erfolgreich aktualisiert.')
            return redirect('admin_workflow_settings')
    else:
        form = WorkflowSettingsForm(instance=settings)

    context = {
        'form': form,
        'section': 'workflow_settings'
    }

    return render(request, 'admin_dashboard/workflow_settings.html', context)


# AJAX-Endpunkte

@login_required
@user_passes_test(is_admin)
def get_user_details(request, user_id):
    """AJAX endpoint to get user details."""
    user = get_object_or_404(User, pk=user_id)

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

    # Abteilungen hinzufügen, falls verfügbar
    try:
        data['departments'] = list(user.profile.departments.values('id', 'name'))
    except:
        data['departments'] = []

    return JsonResponse(data)


@login_required
@user_passes_test(is_admin)
def get_department_details(request, department_id):
    """AJAX endpoint to get department details."""
    department = get_object_or_404(Department, pk=department_id)

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

    # Mitglieder hinzufügen
    try:
        for profile in department.user_profiles.all():
            data['members'].append({
                'id': profile.user.id,
                'username': profile.user.username,
                'name': f"{profile.user.first_name} {profile.user.last_name}".strip() or profile.user.username
            })
    except:
        pass

    return JsonResponse(data)