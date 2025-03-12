# admin_dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group, Permission
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.utils import timezone

from core.permissions import PERMISSION_AREAS, PERMISSION_LEVELS, get_permission_name
from inventory.models import Department, Warehouse, WarehouseAccess
from core.decorators import permission_required

from .forms import SystemSettingsForm, WorkflowSettingsForm


# Hilfsfunktion zur Prüfung von Admin-Berechtigungen
def is_admin(user):
    """Check if user has admin privileges."""
    return user.is_superuser or user.has_perm('admin_dashboard.access_admin')


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    print("Rendering admin dashboard")
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

    context = {
        'stats': stats,
        'recent_activities': recent_activities,
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
def user_edit(request, user_id):
    """Edit a user."""
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        # Benutzerdaten aktualisieren
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.is_active = 'is_active' in request.POST
        user.is_staff = 'is_staff' in request.POST
        user.is_superuser = 'is_superuser' in request.POST

        # Passwort aktualisieren, wenn angegeben
        new_password = request.POST.get('password')
        if new_password:
            user.set_password(new_password)

        user.save()

        # Gruppen aktualisieren
        selected_groups = request.POST.getlist('groups')
        user.groups.clear()
        for group_id in selected_groups:
            try:
                group = Group.objects.get(pk=group_id)
                user.groups.add(group)
            except Group.DoesNotExist:
                pass

        # Abteilungen aktualisieren (falls verfügbar)
        try:
            selected_departments = request.POST.getlist('departments')
            user.profile.departments.clear()
            for dept_id in selected_departments:
                try:
                    dept = Department.objects.get(pk=dept_id)
                    user.profile.departments.add(dept)
                except Department.DoesNotExist:
                    pass
            user.profile.save()
        except:
            # Falls das Profil oder die Departments nicht existieren
            pass

        messages.success(request, f'Benutzer "{user.username}" wurde erfolgreich aktualisiert.')
        return redirect('admin_user_management')

    # Gruppen und Abteilungen für die Auswahl
    groups = Group.objects.all()
    user_groups = user.groups.all()

    try:
        # Abteilungen abrufen, falls verfügbar
        departments = Department.objects.all()
        user_departments = user.profile.departments.all()
    except:
        departments = []
        user_departments = []

    context = {
        'user_obj': user,
        'groups': groups,
        'user_groups': user_groups,
        'departments': departments,
        'user_departments': user_departments,
        'section': 'users'
    }

    return render(request, 'admin_dashboard/user_edit.html', context)


@login_required
@user_passes_test(is_admin)
def user_create(request):
    """Create a new user."""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        is_active = 'is_active' in request.POST
        is_staff = 'is_staff' in request.POST
        is_superuser = 'is_superuser' in request.POST

        # Prüfen, ob der Benutzername bereits existiert
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Benutzername "{username}" existiert bereits.')
            return redirect('admin_user_create')

        # Benutzer erstellen
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        user.is_active = is_active
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.save()

        # Gruppen zuweisen
        selected_groups = request.POST.getlist('groups')
        for group_id in selected_groups:
            try:
                group = Group.objects.get(pk=group_id)
                user.groups.add(group)
            except Group.DoesNotExist:
                pass

        # Abteilungen zuweisen (falls verfügbar)
        try:
            selected_departments = request.POST.getlist('departments')
            for dept_id in selected_departments:
                try:
                    dept = Department.objects.get(pk=dept_id)
                    user.profile.departments.add(dept)
                except Department.DoesNotExist:
                    pass
            user.profile.save()
        except:
            # Falls das Profil oder die Departments nicht existieren
            pass

        messages.success(request, f'Benutzer "{username}" wurde erfolgreich erstellt.')
        return redirect('admin_user_management')

    # Gruppen und Abteilungen für die Auswahl
    groups = Group.objects.all()
    try:
        departments = Department.objects.all()
    except:
        departments = []

    context = {
        'groups': groups,
        'departments': departments,
        'section': 'users'
    }

    return render(request, 'admin_dashboard/user_create.html', context)


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
def group_edit(request, group_id):
    """Edit a group."""
    group = get_object_or_404(Group, pk=group_id)

    if request.method == 'POST':
        # Gruppe aktualisieren
        group.name = request.POST.get('name')
        group.save()

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

    # Berechtigungen für die Auswahl
    permissions_by_area = {}
    for area in PERMISSION_AREAS.keys():
        area_perms = Permission.objects.filter(codename__contains=f'_{area}').order_by('codename')
        permissions_by_area[area] = area_perms

    group_permissions = group.permissions.all()

    context = {
        'group': group,
        'permissions_by_area': permissions_by_area,
        'permission_areas': PERMISSION_AREAS,
        'group_permissions': group_permissions,
        'section': 'groups'
    }

    return render(request, 'admin_dashboard/group_edit.html', context)


@login_required
@user_passes_test(is_admin)
def group_create(request):
    """Create a new group."""
    if request.method == 'POST':
        name = request.POST.get('name')

        # Prüfen, ob die Gruppe bereits existiert
        if Group.objects.filter(name=name).exists():
            messages.error(request, f'Gruppe "{name}" existiert bereits.')
            return redirect('admin_group_create')

        # Gruppe erstellen
        group = Group.objects.create(name=name)

        # Berechtigungen zuweisen
        selected_permissions = request.POST.getlist('permissions')
        for perm_id in selected_permissions:
            try:
                perm = Permission.objects.get(pk=perm_id)
                group.permissions.add(perm)
            except Permission.DoesNotExist:
                pass

        messages.success(request, f'Gruppe "{name}" wurde erfolgreich erstellt.')
        return redirect('admin_group_management')

    # Berechtigungen für die Auswahl
    permissions_by_area = {}
    for area in PERMISSION_AREAS.keys():
        area_perms = Permission.objects.filter(codename__contains=f'_{area}').order_by('codename')
        permissions_by_area[area] = area_perms

    context = {
        'permissions_by_area': permissions_by_area,
        'permission_areas': PERMISSION_AREAS,
        'section': 'groups'
    }

    return render(request, 'admin_dashboard/group_create.html', context)


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
def department_edit(request, department_id):
    """Edit a department."""
    department = get_object_or_404(Department, pk=department_id)

    if request.method == 'POST':
        # Abteilung aktualisieren
        department.name = request.POST.get('name')
        department.code = request.POST.get('code')

        # Manager zuweisen falls angegeben
        manager_id = request.POST.get('manager')
        if manager_id and manager_id != 'none':
            try:
                manager = User.objects.get(pk=manager_id)
                department.manager = manager
            except User.DoesNotExist:
                department.manager = None
        else:
            department.manager = None

        department.save()

        # Mitglieder aktualisieren
        if 'members' in request.POST:
            selected_members = request.POST.getlist('members')

            # Aktuelle Mitglieder abrufen
            current_members = [profile.user.id for profile in department.user_profiles.all()]

            # Mitglieder entfernen, die nicht mehr ausgewählt sind
            for profile in department.user_profiles.all():
                if str(profile.user.id) not in selected_members:
                    department.user_profiles.remove(profile)

            # Neue Mitglieder hinzufügen
            for member_id in selected_members:
                if member_id not in current_members:
                    try:
                        user = User.objects.get(pk=member_id)
                        department.user_profiles.add(user.profile)
                    except User.DoesNotExist:
                        pass

        messages.success(request, f'Abteilung "{department.name}" wurde erfolgreich aktualisiert.')
        return redirect('admin_department_management')

    # Benutzer für die Auswahl
    users = User.objects.all()

    # Aktuelle Mitglieder
    department_members = [profile.user for profile in department.user_profiles.all()]

    context = {
        'department': department,
        'users': users,
        'department_members': department_members,
        'section': 'departments'
    }

    return render(request, 'admin_dashboard/department_edit.html', context)


@login_required
@user_passes_test(is_admin)
def department_create(request):
    """Create a new department."""
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')

        # Prüfen, ob die Abteilung bereits existiert
        if Department.objects.filter(Q(name=name) | Q(code=code)).exists():
            messages.error(request, f'Eine Abteilung mit diesem Namen oder Code existiert bereits.')
            return redirect('admin_department_create')

        # Abteilung erstellen
        department = Department(name=name, code=code)

        # Manager zuweisen falls angegeben
        manager_id = request.POST.get('manager')
        if manager_id and manager_id != 'none':
            try:
                manager = User.objects.get(pk=manager_id)
                department.manager = manager
            except User.DoesNotExist:
                pass

        department.save()

        # Mitglieder hinzufügen
        if 'members' in request.POST:
            selected_members = request.POST.getlist('members')
            for member_id in selected_members:
                try:
                    user = User.objects.get(pk=member_id)
                    department.user_profiles.add(user.profile)
                except User.DoesNotExist:
                    pass

        messages.success(request, f'Abteilung "{name}" wurde erfolgreich erstellt.')
        return redirect('admin_department_management')

    # Benutzer für die Auswahl
    users = User.objects.all()

    context = {
        'users': users,
        'section': 'departments'
    }

    return render(request, 'admin_dashboard/department_create.html', context)


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
        warehouse_id = request.POST.get('warehouse')
        department_id = request.POST.get('department')
        can_view = 'can_view' in request.POST
        can_edit = 'can_edit' in request.POST
        can_manage_stock = 'can_manage_stock' in request.POST

        # Prüfen, ob die Kombination bereits existiert
        if WarehouseAccess.objects.filter(warehouse_id=warehouse_id, department_id=department_id).exists():
            messages.error(request, f'Diese Kombination aus Lager und Abteilung existiert bereits.')
            return redirect('admin_warehouse_access_management')

        # Zugriff erstellen
        access = WarehouseAccess(
            warehouse_id=warehouse_id,
            department_id=department_id,
            can_view=can_view,
            can_edit=can_edit,
            can_manage_stock=can_manage_stock
        )
        access.save()

        messages.success(request, f'Lagerzugriff wurde erfolgreich erstellt.')
        return redirect('admin_warehouse_access_management')

    context = {
        'warehouses': Warehouse.objects.filter(is_active=True),
        'departments': Department.objects.all(),
        'section': 'warehouse_access'
    }

    return render(request, 'admin_dashboard/warehouse_access_create.html', context)


@login_required
@user_passes_test(is_admin)
def warehouse_access_edit(request, access_id):
    """Edit a warehouse access."""
    access = get_object_or_404(WarehouseAccess, pk=access_id)

    if request.method == 'POST':
        # Zugriffsrechte aktualisieren
        access.can_view = 'can_view' in request.POST
        access.can_edit = 'can_edit' in request.POST
        access.can_manage_stock = 'can_manage_stock' in request.POST
        access.save()

        messages.success(request, f'Lagerzugriff wurde erfolgreich aktualisiert.')
        return redirect('admin_warehouse_access_management')

    context = {
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