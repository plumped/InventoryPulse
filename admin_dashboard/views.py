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

from accessmanagement.decorators import is_admin
from accessmanagement.models import WarehouseAccess
from accessmanagement.permissions import PERMISSION_AREAS
from core.models import Tax
from inventory.models import Department, Warehouse

from .forms import SystemSettingsForm, WorkflowSettingsForm, UserCreateForm, UserEditForm, GroupForm, DepartmentForm, \
    WarehouseAccessForm, TaxForm, CompanyAddressForm
from .models import CompanyAddress, CompanyAddressType


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

    try:
        from interfaces.models import SupplierInterface
        interface_stats = {
            'total': SupplierInterface.objects.count(),
            'active': SupplierInterface.objects.filter(is_active=True).count(),
        }
    except (ImportError, Exception):
        interface_stats = None

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
        'section': 'dashboard',
        'interface_stats': interface_stats,
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

    levels = ['view', 'create', 'edit', 'delete', 'approve']

    context = {
        'form': form,
        'permissions_by_area': permissions_by_area,
        'permission_areas': PERMISSION_AREAS,
        'levels': levels,
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
def warehouse_access_delete(request, access_id):
    """Delete a warehouse access."""
    access = get_object_or_404(WarehouseAccess, pk=access_id)

    if request.method == 'POST':
        access.delete()
        messages.success(request, f'Lagerzugriff wurde erfolgreich gelöscht.')
        return redirect('warehouse_access_management')

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


@login_required
@user_passes_test(is_admin)
def tax_management(request):
    """Verwaltung der Mehrwertsteuersätze."""
    taxes = Tax.objects.all().order_by('rate')

    context = {
        'taxes': taxes,
        'section': 'taxes'
    }

    return render(request, 'admin_dashboard/tax_management.html', context)


@login_required
@user_passes_test(is_admin)
def tax_create(request):
    """Neuen Mehrwertsteuersatz erstellen."""
    if request.method == 'POST':
        form = TaxForm(request.POST)
        if form.is_valid():
            tax = form.save()
            messages.success(request, f'Mehrwertsteuersatz "{tax.name}" wurde erfolgreich erstellt.')
            return redirect('admin_tax_management')
    else:
        form = TaxForm()

    context = {
        'form': form,
        'section': 'taxes'
    }

    return render(request, 'admin_dashboard/tax_form.html', context)


@login_required
@user_passes_test(is_admin)
def tax_edit(request, tax_id):
    """Einen Mehrwertsteuersatz bearbeiten."""
    tax = get_object_or_404(Tax, pk=tax_id)

    if request.method == 'POST':
        form = TaxForm(request.POST, instance=tax)
        if form.is_valid():
            tax = form.save()
            messages.success(request, f'Mehrwertsteuersatz "{tax.name}" wurde erfolgreich aktualisiert.')
            return redirect('admin_tax_management')
    else:
        form = TaxForm(instance=tax)

    context = {
        'form': form,
        'tax': tax,
        'section': 'taxes'
    }

    return render(request, 'admin_dashboard/tax_form.html', context)


@login_required
@user_passes_test(is_admin)
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

# In admin_dashboard/views.py
# Fügen Sie Views für die Schnittstellen-Verwaltung hinzu

@login_required
@user_passes_test(is_admin)
def interface_management(request):
    """Verwaltung der Lieferantenschnittstellen im Admin-Dashboard."""
    # Schnittstellentypen abrufen
    from interfaces.models import InterfaceType, SupplierInterface
    
    interface_types = InterfaceType.objects.all().order_by('name')
    
    # Anzahl der Schnittstellen pro Typ ermitteln
    for interface_type in interface_types:
        interface_type.count = SupplierInterface.objects.filter(interface_type=interface_type).count()
    
    # Gesamtanzahl der Schnittstellen
    total_interfaces = SupplierInterface.objects.count()
    active_interfaces = SupplierInterface.objects.filter(is_active=True).count()
    
    # Erfolgsmessung der letzten 30 Tage
    from interfaces.models import InterfaceLog
    from django.utils import timezone
    from django.db.models import Count
    
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    
    # Erfolgreiche vs. fehlgeschlagene Übertragungen
    success_count = InterfaceLog.objects.filter(
        status='success',
        timestamp__gte=thirty_days_ago
    ).count()
    
    failed_count = InterfaceLog.objects.filter(
        status='failed',
        timestamp__gte=thirty_days_ago
    ).count()
    
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
        'section': 'interfaces'
    }
    
    return render(request, 'admin_dashboard/interface_management.html', context)


@login_required
@user_passes_test(is_admin)
def interface_type_management(request):
    """Verwaltung der Schnittstellentypen im Admin-Dashboard."""
    from interfaces.models import InterfaceType, SupplierInterface
    
    interface_types = InterfaceType.objects.all().order_by('name')
    
    # Anzahl der Schnittstellen pro Typ ermitteln
    for interface_type in interface_types:
        interface_type.count = SupplierInterface.objects.filter(interface_type=interface_type).count()
    
    context = {
        'interface_types': interface_types,
        'section': 'interfaces'
    }
    
    return render(request, 'admin_dashboard/interface_type_management.html', context)


@login_required
@user_passes_test(is_admin)
def interface_type_create(request):
    """Neuen Schnittstellentyp erstellen."""
    from interfaces.models import InterfaceType
    from django import forms
    
    class InterfaceTypeForm(forms.ModelForm):
        class Meta:
            model = InterfaceType
            fields = ['name', 'code', 'description', 'is_active']
            widgets = {
                'name': forms.TextInput(attrs={'class': 'form-control'}),
                'code': forms.TextInput(attrs={'class': 'form-control'}),
                'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            }
    
    if request.method == 'POST':
        form = InterfaceTypeForm(request.POST)
        if form.is_valid():
            interface_type = form.save()
            messages.success(request, f'Schnittstellentyp "{interface_type.name}" wurde erfolgreich erstellt.')
            return redirect('admin_interface_type_management')
    else:
        form = InterfaceTypeForm()
    
    context = {
        'form': form,
        'title': 'Neuen Schnittstellentyp erstellen',
        'section': 'interfaces'
    }
    
    return render(request, 'admin_dashboard/interface_type_form.html', context)


@login_required
@user_passes_test(is_admin)
def interface_type_edit(request, type_id):
    """Schnittstellentyp bearbeiten."""
    from interfaces.models import InterfaceType
    from django import forms
    
    interface_type = get_object_or_404(InterfaceType, pk=type_id)
    
    class InterfaceTypeForm(forms.ModelForm):
        class Meta:
            model = InterfaceType
            fields = ['name', 'code', 'description', 'is_active']
            widgets = {
                'name': forms.TextInput(attrs={'class': 'form-control'}),
                'code': forms.TextInput(attrs={'class': 'form-control'}),
                'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            }
    
    if request.method == 'POST':
        form = InterfaceTypeForm(request.POST, instance=interface_type)
        if form.is_valid():
            interface_type = form.save()
            messages.success(request, f'Schnittstellentyp "{interface_type.name}" wurde erfolgreich aktualisiert.')
            return redirect('admin_interface_type_management')
    else:
        form = InterfaceTypeForm(instance=interface_type)
    
    context = {
        'form': form,
        'interface_type': interface_type,
        'title': f'Schnittstellentyp "{interface_type.name}" bearbeiten',
        'section': 'interfaces'
    }
    
    return render(request, 'admin_dashboard/interface_type_form.html', context)


@login_required
@user_passes_test(is_admin)
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
@user_passes_test(is_admin)
def company_address_management(request):
    """Verwaltung der Unternehmensadressen."""
    # Adressen nach Typ gruppieren
    addresses_by_type = []

    for address_type, address_type_display in CompanyAddressType.choices:
        addresses = CompanyAddress.objects.filter(address_type=address_type)
        if addresses.exists() or address_type in ['headquarters', 'billing']:  # Wichtige Typen immer anzeigen
            addresses_by_type.append({
                'type': address_type,
                'display': address_type_display,
                'addresses': addresses,
                'has_default': addresses.filter(is_default=True).exists()
            })

    context = {
        'addresses_by_type': addresses_by_type,
        'section': 'company_addresses'
    }

    return render(request, 'admin_dashboard/company_address_management.html', context)


@login_required
@user_passes_test(is_admin)
def company_address_create(request):
    """Neue Unternehmensadresse erstellen."""
    if request.method == 'POST':
        form = CompanyAddressForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Unternehmensadresse wurde erfolgreich erstellt.')
            return redirect('admin_company_address_management')
    else:
        # Optional: Vorausgewählter Adresstyp aus URL-Parameter
        initial = {}
        address_type = request.GET.get('type')
        if address_type and address_type in dict(CompanyAddressType.choices):
            initial['address_type'] = address_type

        form = CompanyAddressForm(initial=initial)

    context = {
        'form': form,
        'section': 'company_addresses'
    }

    return render(request, 'admin_dashboard/company_address_form.html', context)


@login_required
@user_passes_test(is_admin)
def company_address_edit(request, address_id):
    """Unternehmensadresse bearbeiten."""
    address = get_object_or_404(CompanyAddress, pk=address_id)

    if request.method == 'POST':
        form = CompanyAddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, f'Adresse "{address.name}" wurde erfolgreich aktualisiert.')
            return redirect('admin_company_address_management')
    else:
        form = CompanyAddressForm(instance=address)

    context = {
        'form': form,
        'address': address,
        'section': 'company_addresses'
    }

    return render(request, 'admin_dashboard/company_address_form.html', context)


@login_required
@user_passes_test(is_admin)
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