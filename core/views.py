import csv
import io
import os
import mimetypes
from datetime import datetime, timedelta
from django.http import FileResponse, Http404
from django.utils import timezone
from django.db.models import Sum, Count, F, Case, When, IntegerField
from wsgiref.util import FileWrapper
from django.urls import reverse

from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User, Group, Permission
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import models
from django.db.models import Q, F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.templatetags.static import static

from inventory.models import StockMovement, Warehouse, Department, StockTake, WarehouseAccess
from suppliers.models import Supplier, SupplierProduct
from .decorators import permission_required
from .forms import ProductForm, CategoryForm, SupplierProductImportForm, CategoryImportForm, SupplierImportForm, \
    ProductImportForm, WarehouseImportForm, DepartmentImportForm, WarehouseProductImportForm, ProductPhotoForm, \
    ProductAttachmentForm, ProductVariantTypeForm, ProductVariantForm, SerialNumberForm, BulkSerialNumberForm, \
    BatchNumberForm
from .importers import SupplierProductImporter, CategoryImporter, SupplierImporter, ProductImporter
from .models import Product, Category, ImportLog, ProductWarehouse, ProductPhoto, ProductAttachment, ProductVariantType, \
    ProductVariant, SerialNumber, BatchNumber
from .permissions import PERMISSION_AREAS



@login_required
def dashboard(request):
    # Existierende Daten
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_suppliers = Supplier.objects.count()
    low_stock_count = Product.objects.filter(current_stock__lt=F('minimum_stock')).count()

    # Neue Daten für Lager und Abteilungen
    total_warehouses = Warehouse.objects.filter(is_active=True).count()
    total_departments = Department.objects.count()
    active_stock_takes_count = StockTake.objects.filter(status='in_progress').count()

    # Erweiterte Daten für Tabellen
    recent_movements = StockMovement.objects.select_related('product', 'warehouse', 'created_by').order_by(
        '-created_at')[:10]

    # Kritische Bestände nach Lager
    low_stock_items = ProductWarehouse.objects.select_related('product', 'warehouse').filter(
        quantity__lt=F('product__minimum_stock'),
        warehouse__is_active=True
    )[:10]

    # Aktive Inventuren
    active_stock_takes = StockTake.objects.select_related('warehouse').filter(status='in_progress')[:5]

    # Lagerübersicht mit Produktanzahl
    warehouses = Warehouse.objects.filter(is_active=True)
    for warehouse in warehouses:
        warehouse.product_count = ProductWarehouse.objects.filter(warehouse=warehouse, quantity__gt=0).count()

    context = {
        'total_products': total_products,
        'total_categories': total_categories,
        'total_suppliers': total_suppliers,
        'low_stock_count': low_stock_count,
        'total_warehouses': total_warehouses,
        'total_departments': total_departments,
        'active_stock_takes_count': active_stock_takes_count,
        'recent_movements': recent_movements,
        'low_stock_items': low_stock_items,
        'active_stock_takes': active_stock_takes,
        'warehouses': warehouses[:5],  # Nur die ersten 5 Lager anzeigen
    }

    return render(request, 'dashboard.html', context)


@login_required
@permission_required('product', 'view')
def product_list(request):
    """List all products with filtering and search."""
    products_list = Product.objects.select_related('category').all()

    # Suche
    search_query = request.GET.get('search', '')
    if search_query:
        products_list = products_list.filter(
            Q(name__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )

    # Kategorie-Filter
    category_id = request.GET.get('category', '')
    if category_id:
        products_list = products_list.filter(category_id=category_id)

    # Bestandsstatus-Filter
    stock_status = request.GET.get('stock_status', '')
    if stock_status == 'low':
        products_list = products_list.filter(current_stock__lte=F('minimum_stock'), current_stock__gt=0)
    elif stock_status == 'ok':
        products_list = products_list.filter(current_stock__gt=F('minimum_stock'))
    elif stock_status == 'out':
        products_list = products_list.filter(current_stock=0)

    # Sortierung
    products_list = products_list.order_by('name')

    # Paginierung
    paginator = Paginator(products_list, 25)  # 25 Produkte pro Seite
    page = request.GET.get('page')
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    # Alle Kategorien für den Filter
    categories = Category.objects.all().order_by('name')

    context = {
        'products': products,
        'categories': categories,
        'search_query': search_query,
        'category_id': category_id,
        'stock_status': stock_status,
    }

    return render(request, 'core/product_list.html', context)


@login_required
@permission_required('product', 'view')
def low_stock_list(request):
    """Show products with low stock (current_stock <= minimum_stock)."""
    low_stock_products = Product.objects.select_related('category').filter(
        current_stock__lte=F('minimum_stock')
    ).order_by('name')

    context = {
        'products': low_stock_products,
        'title': 'Kritische Bestände',
    }

    return render(request, 'core/low_stock_list.html', context)


@login_required
@permission_required('product', 'view')
def product_detail(request, pk):
    """Show details for a specific product."""
    product = get_object_or_404(Product, pk=pk)

    # Lieferanteninformationen
    supplier_products = SupplierProduct.objects.filter(product=product).select_related('supplier')

    # Bestandsbewegungen
    movements = StockMovement.objects.filter(product=product).select_related('created_by').order_by('-created_at')[:20]

    context = {
        'product': product,
        'supplier_products': supplier_products,
        'movements': movements,
    }

    return render(request, 'core/product_detail.html', context)


@login_required
@permission_required('product', 'create')
def product_create(request):
    """Create a new product."""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()

            # Bestandsbewegung für Anfangsbestand erstellen, wenn > 0
            initial_stock = form.cleaned_data.get('current_stock')
            if initial_stock > 0:
                StockMovement.objects.create(
                    product=product,
                    quantity=initial_stock,
                    movement_type='in',
                    reference='Anfangsbestand',
                    created_by=request.user
                )

            messages.success(request, f'Produkt "{product.name}" wurde erfolgreich erstellt.')
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductForm()

    context = {
        'form': form,
    }

    return render(request, 'core/product_form.html', context)


@login_required
@permission_required('product', 'edit')
def product_update(request, pk):
    """Update an existing product."""
    product = get_object_or_404(Product, pk=pk)
    old_stock = product.current_stock

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            new_stock = form.cleaned_data.get('current_stock')

            # Create stock movement for stock change if stock has changed
            if new_stock != old_stock:
                # Try to get a warehouse associated with the product
                try:
                    # First, try to get a warehouse from ProductWarehouse
                    product_warehouse = ProductWarehouse.objects.filter(product=product).first()

                    # If no ProductWarehouse exists, get the first warehouse
                    if not product_warehouse:
                        warehouse = Warehouse.objects.first()
                    else:
                        warehouse = product_warehouse.warehouse

                    # If still no warehouse, create a default one
                    if not warehouse:
                        warehouse = Warehouse.objects.create(
                            name='Hauptlager',
                            code='MAIN'
                        )

                    # Create StockMovement
                    StockMovement.objects.create(
                        product=product,
                        warehouse=warehouse,
                        quantity=abs(new_stock - old_stock),  # Use absolute value
                        movement_type='adj',  # Adjustment
                        reference='Manuelle Korrektur',
                        notes=f'Bestandskorrektur von {old_stock} auf {new_stock}',
                        created_by=request.user
                    )

                except Exception as e:
                    # Log the error or handle it appropriately
                    messages.error(request, f'Fehler bei der Erstellung der Lagerbewegung: {str(e)}')

            # Save the product
            product = form.save()
            messages.success(request, f'Produkt "{product.name}" wurde erfolgreich aktualisiert.')
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductForm(instance=product)

    context = {
        'form': form,
    }

    return render(request, 'core/product_form.html', context)


@login_required
@permission_required('product', 'view')
def category_list(request):
    """List all categories."""
    categories = Category.objects.all().order_by('name')

    # Für jede Kategorie die Anzahl der zugehörigen Produkte ermitteln
    categories_with_counts = []
    for category in categories:
        product_count = Product.objects.filter(category=category).count()
        categories_with_counts.append({
            'category': category,
            'product_count': product_count
        })

    context = {
        'categories': categories_with_counts,
    }

    return render(request, 'core/category_list.html', context)


@login_required
@permission_required('product', 'create')
def category_create(request):
    """Create a new category."""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Kategorie "{category.name}" wurde erfolgreich erstellt.')
            return redirect('category_list')
    else:
        form = CategoryForm()

    context = {
        'form': form,
    }

    return render(request, 'core/category_form.html', context)


@login_required
def profile(request):
    """User profile view."""
    # Hier könnten Sie die Form für die Profilbearbeitung hinzufügen
    # Für das MVP zeigen wir nur grundlegende Benutzerinformationen an

    context = {
        'user': request.user,
    }

    return render(request, 'auth/profile.html', context)


@login_required
@permission_required('product', 'edit')
def category_update(request, pk):
    """Update an existing category."""
    category = get_object_or_404(Category, pk=pk)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Kategorie "{category.name}" wurde erfolgreich aktualisiert.')
            return redirect('category_list')
    else:
        form = CategoryForm(instance=category)

    context = {
        'form': form,
        'category': category,
    }

    return render(request, 'core/category_form.html', context)


# Ergänzung zu core/views.py

@login_required
@permission_required('import', 'view')
def import_dashboard(request):
    """Dashboard for all import functionality."""
    # Get recent import logs
    recent_imports = ImportLog.objects.all()[:10]

    context = {
        'recent_imports': recent_imports,
    }

    return render(request, 'core/import/dashboard.html', context)


@login_required
@permission_required('import', 'create')
def import_products(request):
    """Import products from CSV."""
    if request.method == 'POST':
        form = ProductImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file_obj = request.FILES['file']
                delimiter = form.cleaned_data['delimiter']
                encoding = form.cleaned_data['encoding']
                skip_header = form.cleaned_data['skip_header']
                update_existing = form.cleaned_data['update_existing']
                default_category = form.cleaned_data['default_category']

                importer = ProductImporter(
                    file_obj=file_obj,
                    delimiter=delimiter,
                    encoding=encoding,
                    skip_header=skip_header,
                    update_existing=update_existing,
                    default_category=default_category,
                    user=request.user
                )

                import_log = importer.run_import()

                messages.success(
                    request,
                    f"Import abgeschlossen. {import_log.successful_rows} von {import_log.total_rows} "
                    f"Produkten erfolgreich importiert ({import_log.success_rate()}%)."
                )

                if import_log.failed_rows > 0:
                    messages.warning(
                        request,
                        f"{import_log.failed_rows} Zeilen konnten nicht importiert werden. "
                        f"Siehe Details für weitere Informationen."
                    )

                return redirect('import_log_detail', pk=import_log.pk)

            except Exception as e:
                messages.error(request, f"Fehler beim Import: {str(e)}")
    else:
        form = ProductImportForm()

    context = {
        'form': form,
        'title': 'Produkte importieren',
        'template_file_url': static('files/product_import_template.csv'),
    }

    return render(request, 'core/import/import_form.html', context)


@login_required
@permission_required('import', 'create')
def import_suppliers(request):
    """Import suppliers from CSV."""
    if request.method == 'POST':
        form = SupplierImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file_obj = request.FILES['file']
                delimiter = form.cleaned_data['delimiter']
                encoding = form.cleaned_data['encoding']
                skip_header = form.cleaned_data['skip_header']
                update_existing = form.cleaned_data['update_existing']

                importer = SupplierImporter(
                    file_obj=file_obj,
                    delimiter=delimiter,
                    encoding=encoding,
                    skip_header=skip_header,
                    update_existing=update_existing,
                    user=request.user
                )

                import_log = importer.run_import()

                messages.success(
                    request,
                    f"Import abgeschlossen. {import_log.successful_rows} von {import_log.total_rows} "
                    f"Lieferanten erfolgreich importiert ({import_log.success_rate()}%)."
                )

                if import_log.failed_rows > 0:
                    messages.warning(
                        request,
                        f"{import_log.failed_rows} Zeilen konnten nicht importiert werden. "
                        f"Siehe Details für weitere Informationen."
                    )

                return redirect('import_log_detail', pk=import_log.pk)

            except Exception as e:
                messages.error(request, f"Fehler beim Import: {str(e)}")
    else:
        form = SupplierImportForm()

    context = {
        'form': form,
        'title': 'Lieferanten importieren',
        'template_file_url': static('files/supplier_import_template.csv'),
    }

    return render(request, 'core/import/import_form.html', context)


@login_required
@permission_required('import', 'create')
def import_categories(request):
    """Import categories from CSV."""
    if request.method == 'POST':
        form = CategoryImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file_obj = request.FILES['file']
                delimiter = form.cleaned_data['delimiter']
                encoding = form.cleaned_data['encoding']
                skip_header = form.cleaned_data['skip_header']
                update_existing = form.cleaned_data['update_existing']

                importer = CategoryImporter(
                    file_obj=file_obj,
                    delimiter=delimiter,
                    encoding=encoding,
                    skip_header=skip_header,
                    update_existing=update_existing,
                    user=request.user
                )

                import_log = importer.run_import()

                messages.success(
                    request,
                    f"Import abgeschlossen. {import_log.successful_rows} von {import_log.total_rows} "
                    f"Kategorien erfolgreich importiert ({import_log.success_rate()}%)."
                )

                if import_log.failed_rows > 0:
                    messages.warning(
                        request,
                        f"{import_log.failed_rows} Zeilen konnten nicht importiert werden. "
                        f"Siehe Details für weitere Informationen."
                    )

                return redirect('import_log_detail', pk=import_log.pk)

            except Exception as e:
                messages.error(request, f"Fehler beim Import: {str(e)}")
    else:
        form = CategoryImportForm()

    context = {
        'form': form,
        'title': 'Kategorien importieren',
        'template_file_url': static('files/category_import_template.csv'),
    }

    return render(request, 'core/import/import_form.html', context)


@login_required
@permission_required('import', 'create')
def import_supplier_products(request):
    """Import supplier-product relationships from CSV."""
    if request.method == 'POST':
        form = SupplierProductImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file_obj = request.FILES['file']
                delimiter = form.cleaned_data['delimiter']
                encoding = form.cleaned_data['encoding']
                skip_header = form.cleaned_data['skip_header']
                update_existing = form.cleaned_data['update_existing']

                importer = SupplierProductImporter(
                    file_obj=file_obj,
                    delimiter=delimiter,
                    encoding=encoding,
                    skip_header=skip_header,
                    update_existing=update_existing,
                    user=request.user
                )

                import_log = importer.run_import()

                messages.success(
                    request,
                    f"Import abgeschlossen. {import_log.successful_rows} von {import_log.total_rows} "
                    f"Produkt-Lieferanten-Zuordnungen erfolgreich importiert ({import_log.success_rate()}%)."
                )

                if import_log.failed_rows > 0:
                    messages.warning(
                        request,
                        f"{import_log.failed_rows} Zeilen konnten nicht importiert werden. "
                        f"Siehe Details für weitere Informationen."
                    )

                return redirect('import_log_detail', pk=import_log.pk)

            except Exception as e:
                messages.error(request, f"Fehler beim Import: {str(e)}")
    else:
        form = SupplierProductImportForm()

    context = {
        'form': form,
        'title': 'Produkt-Lieferanten-Zuordnungen importieren',
        'template_file_url': static('files/supplier_product_import_template.csv'),
    }

    return render(request, 'core/import/import_form.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
@permission_required('import', 'create')
def import_warehouses(request):
    """Import warehouses from CSV file."""
    if request.method == 'POST':
        form = WarehouseImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']

            # Überprüfen des Dateityps
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Bitte laden Sie eine CSV-Datei hoch.')
                return redirect('import_warehouses')

            # Datei in Speicher lesen
            file_data = csv_file.read().decode('utf-8')

            # Import-Log erstellen
            import_log = ImportLog.objects.create(
                file_name=csv_file.name,
                import_type='warehouses',
                started_by=request.user,
                status='processing'
            )

            try:
                lines = file_data.split('\n')
                # CSV-Header überprüfen
                header = lines[0].strip().split(',')
                expected_header = ['name', 'location', 'description', 'is_active']

                if not all(column in header for column in expected_header):
                    import_log.status = 'failed'
                    import_log.notes = f'Ungültiger CSV-Header. Erwarteter Header: {", ".join(expected_header)}'
                    import_log.save()
                    messages.error(request, import_log.notes)
                    return redirect('import_warehouses')

                # Index der Spalten ermitteln
                name_idx = header.index('name')
                location_idx = header.index('location')
                description_idx = header.index('description') if 'description' in header else None
                is_active_idx = header.index('is_active') if 'is_active' in header else None

                # Import starten
                created_count = 0
                updated_count = 0
                error_count = 0
                error_msgs = []

                # CSV-Zeilen verarbeiten (ohne Header)
                for i, line in enumerate(lines[1:], 1):
                    if not line.strip():  # Leere Zeile überspringen
                        continue

                    try:
                        # Zeile parsen
                        fields = line.strip().split(',')

                        name = fields[name_idx].strip()
                        location = fields[location_idx].strip()
                        description = fields[
                            description_idx].strip() if description_idx is not None and description_idx < len(
                            fields) else ''

                        # is_active Feld parsen
                        is_active = True  # Standardwert
                        if is_active_idx is not None and is_active_idx < len(fields):
                            is_active_value = fields[is_active_idx].strip().lower()
                            is_active = is_active_value in ['true', '1', 'yes', 'ja', 'y', 'j']

                        # Lager erstellen oder aktualisieren
                        warehouse, created = Warehouse.objects.update_or_create(
                            name=name,
                            defaults={
                                'location': location,
                                'description': description,
                                'is_active': is_active
                            }
                        )

                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                    except Exception as e:
                        error_count += 1
                        error_msg = f'Fehler in Zeile {i + 1}: {str(e)}'
                        error_msgs.append(error_msg)

                # Import-Log aktualisieren
                import_log.status = 'completed' if error_count == 0 else 'completed_with_errors'
                import_log.rows_processed = created_count + updated_count + error_count
                import_log.rows_created = created_count
                import_log.rows_updated = updated_count
                import_log.rows_error = error_count
                import_log.notes = f"Import abgeschlossen: {created_count} erstellt, {updated_count} aktualisiert, {error_count} Fehler"

                if error_msgs:
                    import_log.error_details = '\n'.join(error_msgs)

                import_log.save()

                if error_count > 0:
                    messages.warning(request,
                                     f'Import mit Fehlern abgeschlossen. {created_count} Lager erstellt, {updated_count} aktualisiert, {error_count} Fehler.')
                else:
                    messages.success(request,
                                     f'Import erfolgreich abgeschlossen. {created_count} Lager erstellt, {updated_count} aktualisiert.')

                return redirect('import_log_detail', pk=import_log.pk)

            except Exception as e:
                import_log.status = 'failed'
                import_log.notes = f'Fehler beim Import: {str(e)}'
                import_log.save()
                messages.error(request, import_log.notes)
                return redirect('import_warehouses')
    else:
        form = WarehouseImportForm()

    context = {
        'form': form,
        'title': 'Lager importieren',
        'description': 'Importieren Sie Lager aus einer CSV-Datei.',
        'expected_format': 'name,location,description,is_active',
        'example': 'Hauptlager,Berlin,Unser Hauptlager,true',
        'required_columns': ['name', 'location'],
        'optional_columns': ['description', 'is_active'],
    }

    return render(request, 'core/import/import_form.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
@permission_required('import', 'create')
def import_departments(request):
    """Import departments from CSV file."""
    if request.method == 'POST':
        form = DepartmentImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']

            # Überprüfen des Dateityps
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Bitte laden Sie eine CSV-Datei hoch.')
                return redirect('import_departments')

            # Datei in Speicher lesen
            file_data = csv_file.read().decode('utf-8')

            # Import-Log erstellen
            import_log = ImportLog.objects.create(
                file_name=csv_file.name,
                import_type='departments',
                started_by=request.user,
                status='processing'
            )

            try:
                lines = file_data.split('\n')
                # CSV-Header überprüfen
                header = lines[0].strip().split(',')
                expected_header = ['name', 'code', 'manager_username']

                if not all(column in header for column in expected_header):
                    import_log.status = 'failed'
                    import_log.notes = f'Ungültiger CSV-Header. Erwarteter Header: {", ".join(expected_header)}'
                    import_log.save()
                    messages.error(request, import_log.notes)
                    return redirect('import_departments')

                # Index der Spalten ermitteln
                name_idx = header.index('name')
                code_idx = header.index('code')
                manager_username_idx = header.index('manager_username')

                # Import starten
                created_count = 0
                updated_count = 0
                error_count = 0
                error_msgs = []

                # CSV-Zeilen verarbeiten (ohne Header)
                for i, line in enumerate(lines[1:], 1):
                    if not line.strip():  # Leere Zeile überspringen
                        continue

                    try:
                        # Zeile parsen
                        fields = line.strip().split(',')

                        name = fields[name_idx].strip()
                        code = fields[code_idx].strip()
                        manager_username = fields[manager_username_idx].strip() if manager_username_idx < len(
                            fields) else ''

                        # Manager finden, falls angegeben
                        manager = None
                        if manager_username:
                            try:
                                manager = User.objects.get(username=manager_username)
                            except User.DoesNotExist:
                                error_count += 1
                                error_msg = f'Fehler in Zeile {i + 1}: Benutzer "{manager_username}" nicht gefunden.'
                                error_msgs.append(error_msg)
                                continue

                        # Abteilung erstellen oder aktualisieren
                        department, created = Department.objects.update_or_create(
                            code=code,
                            defaults={
                                'name': name,
                                'manager': manager
                            }
                        )

                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                    except Exception as e:
                        error_count += 1
                        error_msg = f'Fehler in Zeile {i + 1}: {str(e)}'
                        error_msgs.append(error_msg)

                # Import-Log aktualisieren
                import_log.status = 'completed' if error_count == 0 else 'completed_with_errors'
                import_log.rows_processed = created_count + updated_count + error_count
                import_log.rows_created = created_count
                import_log.rows_updated = updated_count
                import_log.rows_error = error_count
                import_log.notes = f"Import abgeschlossen: {created_count} erstellt, {updated_count} aktualisiert, {error_count} Fehler"

                if error_msgs:
                    import_log.error_details = '\n'.join(error_msgs)

                import_log.save()

                if error_count > 0:
                    messages.warning(request,
                                     f'Import mit Fehlern abgeschlossen. {created_count} Abteilungen erstellt, {updated_count} aktualisiert, {error_count} Fehler.')
                else:
                    messages.success(request,
                                     f'Import erfolgreich abgeschlossen. {created_count} Abteilungen erstellt, {updated_count} aktualisiert.')

                return redirect('import_log_detail', pk=import_log.pk)

            except Exception as e:
                import_log.status = 'failed'
                import_log.notes = f'Fehler beim Import: {str(e)}'
                import_log.save()
                messages.error(request, import_log.notes)
                return redirect('import_departments')
    else:
        form = DepartmentImportForm()

    context = {
        'form': form,
        'title': 'Abteilungen importieren',
        'description': 'Importieren Sie Abteilungen aus einer CSV-Datei.',
        'expected_format': 'name,code,manager_username',
        'example': 'Vertrieb,VT01,max.mustermann',
        'required_columns': ['name', 'code'],
        'optional_columns': ['manager_username'],
    }

    return render(request, 'core/import/import_form.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
@permission_required('import', 'create')
def import_warehouse_products(request):
    """Import product stock to warehouses from CSV file."""
    if request.method == 'POST':
        form = WarehouseProductImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']

            # Überprüfen des Dateityps
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Bitte laden Sie eine CSV-Datei hoch.')
                return redirect('import_warehouse_products')

            # Datei in Speicher lesen
            file_data = csv_file.read().decode('utf-8')

            # Import-Log erstellen
            import_log = ImportLog.objects.create(
                file_name=csv_file.name,
                import_type='warehouse_products',
                started_by=request.user,
                status='processing'
            )

            try:
                lines = file_data.split('\n')
                # CSV-Header überprüfen
                header = lines[0].strip().split(',')
                expected_header = ['product_sku', 'warehouse_name', 'quantity', 'reference']

                if not all(column in header for column in expected_header[:3]):  # Referenz ist optional
                    import_log.status = 'failed'
                    import_log.notes = f'Ungültiger CSV-Header. Erwarteter Header: {", ".join(expected_header[:3])}'
                    import_log.save()
                    messages.error(request, import_log.notes)
                    return redirect('import_warehouse_products')

                # Index der Spalten ermitteln
                product_sku_idx = header.index('product_sku')
                warehouse_name_idx = header.index('warehouse_name')
                quantity_idx = header.index('quantity')
                reference_idx = header.index('reference') if 'reference' in header else None

                # Zugriffsrechte prüfen und verfügbare Lager für den Benutzer ermitteln
                if request.user.is_superuser:
                    accessible_warehouses = Warehouse.objects.filter(is_active=True)
                else:
                    user_departments = request.user.departments.all()
                    warehouse_access = WarehouseAccess.objects.filter(
                        department__in=user_departments,
                        can_manage_stock=True
                    ).values_list('warehouse', flat=True)
                    accessible_warehouses = Warehouse.objects.filter(pk__in=warehouse_access, is_active=True)

                # Import starten
                created_count = 0
                updated_count = 0
                error_count = 0
                error_msgs = []

                # CSV-Zeilen verarbeiten (ohne Header)
                for i, line in enumerate(lines[1:], 1):
                    if not line.strip():  # Leere Zeile überspringen
                        continue

                    try:
                        # Zeile parsen
                        fields = line.strip().split(',')

                        product_sku = fields[product_sku_idx].strip()
                        warehouse_name = fields[warehouse_name_idx].strip()
                        quantity_str = fields[quantity_idx].strip()
                        reference = fields[reference_idx].strip() if reference_idx is not None and reference_idx < len(
                            fields) else 'CSV-Import'

                        # Produkt und Lager finden
                        try:
                            product = Product.objects.get(sku=product_sku)
                        except Product.DoesNotExist:
                            error_count += 1
                            error_msg = f'Fehler in Zeile {i + 1}: Produkt mit SKU "{product_sku}" nicht gefunden.'
                            error_msgs.append(error_msg)
                            continue

                        try:
                            warehouse = Warehouse.objects.get(name=warehouse_name, is_active=True)
                        except Warehouse.DoesNotExist:
                            error_count += 1
                            error_msg = f'Fehler in Zeile {i + 1}: Lager "{warehouse_name}" nicht gefunden oder inaktiv.'
                            error_msgs.append(error_msg)
                            continue

                        # Prüfen, ob der Benutzer Zugriff auf das Lager hat
                        if warehouse not in accessible_warehouses:
                            error_count += 1
                            error_msg = f'Fehler in Zeile {i + 1}: Keine Berechtigung für Lager "{warehouse_name}".'
                            error_msgs.append(error_msg)
                            continue

                        # Menge parsen
                        try:
                            quantity = Decimal(quantity_str)
                            if quantity < 0:
                                raise ValueError("Menge kann nicht negativ sein")
                        except ValueError:
                            error_count += 1
                            error_msg = f'Fehler in Zeile {i + 1}: Ungültige Menge "{quantity_str}".'
                            error_msgs.append(error_msg)
                            continue

                        # Aktuelle Bestandsmenge im Lager ermitteln
                        try:
                            product_warehouse = ProductWarehouse.objects.get(product=product, warehouse=warehouse)
                            current_quantity = product_warehouse.quantity
                            is_new = False
                        except ProductWarehouse.DoesNotExist:
                            current_quantity = Decimal('0')
                            is_new = True

                        # Bestandskorrektur nur vornehmen, wenn sich die Menge ändert
                        if current_quantity != quantity:
                            # Bestandsbewegung erstellen
                            StockMovement.objects.create(
                                product=product,
                                warehouse=warehouse,
                                quantity=quantity,
                                movement_type='adj',
                                reference=reference,
                                notes=f'CSV-Import: Bestand von {current_quantity} auf {quantity} angepasst',
                                created_by=request.user
                            )

                            # Bestand im Lager aktualisieren
                            if is_new:
                                ProductWarehouse.objects.create(
                                    product=product,
                                    warehouse=warehouse,
                                    quantity=quantity
                                )
                                created_count += 1
                            else:
                                product_warehouse.quantity = quantity
                                product_warehouse.save()
                                updated_count += 1

                            # Gesamtbestand des Produkts aktualisieren
                            total_stock = ProductWarehouse.objects.filter(product=product).aggregate(
                                total=models.Sum('quantity'))['total'] or 0
                            product.current_stock = total_stock
                            product.save()
                        else:
                            # Keine Änderung notwendig
                            if is_new:
                                created_count += 1
                            else:
                                updated_count += 1

                    except Exception as e:
                        error_count += 1
                        error_msg = f'Fehler in Zeile {i + 1}: {str(e)}'
                        error_msgs.append(error_msg)

                # Import-Log aktualisieren
                import_log.status = 'completed' if error_count == 0 else 'completed_with_errors'
                import_log.rows_processed = created_count + updated_count + error_count
                import_log.rows_created = created_count
                import_log.rows_updated = updated_count
                import_log.rows_error = error_count
                import_log.notes = f"Import abgeschlossen: {created_count} erstellt, {updated_count} aktualisiert, {error_count} Fehler"

                if error_msgs:
                    import_log.error_details = '\n'.join(error_msgs)

                import_log.save()

                if error_count > 0:
                    messages.warning(request,
                                     f'Import mit Fehlern abgeschlossen. {created_count} Bestände erstellt, {updated_count} aktualisiert, {error_count} Fehler.')
                else:
                    messages.success(request,
                                     f'Import erfolgreich abgeschlossen. {created_count} Bestände erstellt, {updated_count} aktualisiert.')

                return redirect('import_log_detail', pk=import_log.pk)

            except Exception as e:
                import_log.status = 'failed'
                import_log.notes = f'Fehler beim Import: {str(e)}'
                import_log.save()
                messages.error(request, import_log.notes)
                return redirect('import_warehouse_products')
    else:
        form = WarehouseProductImportForm()

    context = {
        'form': form,
        'title': 'Produkt-Lager-Bestände importieren',
        'description': 'Importieren Sie Produktbestände für Lager aus einer CSV-Datei.',
        'expected_format': 'product_sku,warehouse_name,quantity,reference',
        'example': 'P1001,Hauptlager,25.5,Anfangsbestand',
        'required_columns': ['product_sku', 'warehouse_name', 'quantity'],
        'optional_columns': ['reference'],
    }

    return render(request, 'core/import/import_form.html', context)


# Updated import-related views in core/views.py

# Updated import-related views in core/views.py

@login_required
@permission_required('import', 'view')
def import_log_list(request):
    """List all import logs."""
    # Base queryset
    queryset = ImportLog.objects.all()

    # Apply filters
    if 'search' in request.GET and request.GET['search']:
        search = request.GET['search']
        queryset = queryset.filter(file_name__icontains=search)

    if 'status' in request.GET and request.GET['status']:
        status = request.GET['status']
        queryset = queryset.filter(status=status)

    if 'user' in request.GET and request.GET['user']:
        user_id = request.GET['user']
        queryset = queryset.filter(created_by_id=user_id)

    if 'type' in request.GET and request.GET['type']:
        import_type = request.GET['type']
        queryset = queryset.filter(import_type=import_type)

    # Apply sorting
    sort_param = request.GET.get('sort', '-created_at')
    if sort_param:
        queryset = queryset.order_by(sort_param)

    # Pagination
    paginator = Paginator(queryset, 20)
    page = request.GET.get('page')
    try:
        import_logs = paginator.page(page)
    except PageNotAnInteger:
        import_logs = paginator.page(1)
    except EmptyPage:
        import_logs = paginator.page(paginator.num_pages)

    context = {
        'import_logs': import_logs,
        'users': User.objects.all(),
    }

    return render(request, 'core/import/import_log_list.html', context)


@login_required
@permission_required('import', 'view')
def import_log_detail(request, pk):
    """Show details of an import log."""
    log = get_object_or_404(ImportLog, pk=pk)
    errors = log.errors.all() if hasattr(log, 'errors') else ImportError.objects.filter(import_log=log)

    context = {
        'log': log,
        'errors': errors,
    }

    return render(request, 'core/import/import_log_detail.html', context)


@login_required
@permission_required('import', 'view')
def download_error_file(request, log_id):
    """Download the error file for an import log."""
    log = get_object_or_404(ImportLog, pk=log_id)

    # Check if actual error file exists and return it if it does
    if log.error_file and log.error_file.name:
        response = HttpResponse(log.error_file.read(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{log.file_name}_errors.csv"'
        return response

    # Otherwise generate a CSV with errors
    errors = log.errors.all() if hasattr(log, 'errors') else ImportError.objects.filter(import_log=log)

    if not errors.exists():
        messages.warning(request, 'Keine Fehler zum Herunterladen vorhanden.')
        return redirect('import_log_detail', pk=log_id)

    # CSV-Datei erstellen
    response = HttpResponse(content_type='text/csv')
    response[
        'Content-Disposition'] = f'attachment; filename="import_fehler_{log.pk}_{datetime.now().strftime("%Y%m%d")}.csv"'

    # CSV-Writer einrichten
    writer = csv.writer(response)

    # Header schreiben
    writer.writerow(['Zeile', 'Feld', 'Fehler', 'Wert'])

    # Fehler schreiben
    for error in errors:
        writer.writerow([error.row_number, error.field_name, error.error_message, error.field_value])

    return response


@login_required
@permission_required('import', 'delete')
def delete_import_log(request, log_id):
    """Delete an import log."""
    if request.method == 'POST':
        log = get_object_or_404(ImportLog, pk=log_id)

        # Save name for confirmation message
        log_name = f"Import #{log.pk} ({log.import_type})"

        # Delete all errors associated with the log
        from core.models import ImportError as ImportErrorModel
        ImportErrorModel.objects.filter(import_log=log).delete()

        # Delete the log
        log.delete()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # For AJAX requests
            return JsonResponse({'success': True, 'message': f'{log_name} wurde gelöscht.'})
        else:
            # For normal requests
            messages.success(request, f'{log_name} wurde gelöscht.')
            return redirect('import_log_list')

    # If not a POST request, 405 Method Not Allowed
    return JsonResponse({'success': False, 'message': 'Nur POST-Anfragen sind erlaubt.'}, status=405)


@login_required
@permission_required('import', 'delete')
def bulk_delete_import_logs(request):
    """Delete multiple import logs."""
    if request.method == 'POST':
        # Get IDs from the request (comma-separated list)
        ids_str = request.POST.get('ids', '')

        if not ids_str:
            return JsonResponse({'success': False, 'message': 'Keine IDs angegeben.'}, status=400)

        try:
            # Convert IDs to a list
            ids = [int(id_str.strip()) for id_str in ids_str.split(',') if id_str.strip()]

            # Delete errors associated with the logs
            from core.models import ImportError as ImportErrorModel
            ImportErrorModel.objects.filter(import_log_id__in=ids).delete()

            # Delete logs
            deleted_count = ImportLog.objects.filter(pk__in=ids).delete()[0]

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # For AJAX requests
                return JsonResponse({'success': True, 'message': f'{deleted_count} Import-Logs wurden gelöscht.'})
            else:
                # For normal requests
                messages.success(request, f'{deleted_count} Import-Logs wurden gelöscht.')
                return redirect('import_log_list')

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Fehler beim Löschen: {str(e)}'}, status=500)

    # If not a POST request, 405 Method Not Allowed
    return JsonResponse({'success': False, 'message': 'Nur POST-Anfragen sind erlaubt.'}, status=405)


@login_required
@permission_required('report', 'view')
def export_import_logs(request):
    """Export import logs to CSV or Excel."""
    # Base queryset
    queryset = ImportLog.objects.all()

    # Apply filters
    import_type = request.GET.get('type')
    if import_type:
        queryset = queryset.filter(import_type=import_type)

    # Check for specific IDs
    ids_str = request.GET.get('ids', '')
    if ids_str:
        ids = [int(id_str.strip()) for id_str in ids_str.split(',') if id_str.strip()]
        queryset = queryset.filter(pk__in=ids)

    # Determine format
    export_format = request.GET.get('format', 'csv').lower()

    # CSV export
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="import_logs_{datetime.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)

        # Write header
        writer.writerow(['ID', 'Type', 'Filename', 'Status', 'Total Rows', 'Successful Rows',
                         'Error Rows', 'Success Rate', 'User', 'Created At'])

        # Write data
        for log in queryset:
            writer.writerow([
                log.pk,
                log.import_type,
                log.file_name,
                log.status,
                log.total_records,
                log.success_count,
                log.error_count,
                f"{log.success_rate()}%",
                log.created_by.username if log.created_by else 'System',
                log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

        return response

    # Excel export
    elif export_format == 'xlsx':
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            messages.error(request, 'Excel-Export ist nicht verfügbar. Bitte installieren Sie openpyxl.')
            return redirect('import_log_list')

        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Import Logs"

        # Define headers
        headers = ['ID', 'Type', 'Filename', 'Status', 'Total Rows', 'Successful Rows',
                   'Error Rows', 'Success Rate', 'User', 'Created At']

        # Define styles for header
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")

        # Write and format header
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill

        # Write data
        for row_num, log in enumerate(queryset, 2):
            ws.cell(row=row_num, column=1, value=log.pk)
            ws.cell(row=row_num, column=2, value=log.import_type)
            ws.cell(row=row_num, column=3, value=log.file_name)
            ws.cell(row=row_num, column=4, value=log.status)
            ws.cell(row=row_num, column=5, value=log.total_records)
            ws.cell(row=row_num, column=6, value=log.success_count)
            ws.cell(row=row_num, column=7, value=log.error_count)
            ws.cell(row=row_num, column=8, value=f"{log.success_rate()}%")
            ws.cell(row=row_num, column=9, value=log.created_by.username if log.created_by else 'System')
            ws.cell(row=row_num, column=10, value=log.created_at.strftime('%Y-%m-%d %H:%M:%S'))

        # Adjust column widths
        for col_num, header in enumerate(headers, 1):
            column_letter = openpyxl.utils.get_column_letter(col_num)
            # Minimum width based on header + some space
            max_length = len(header) + 2

            # Check width based on data
            for row_num in range(2, len(queryset) + 2):
                cell = ws.cell(row=row_num, column=col_num)
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)) + 2)

            ws.column_dimensions[column_letter].width = max_length

        # Write Excel file to a BytesIO stream
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # Create response
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="import_logs_{datetime.now().strftime("%Y%m%d")}.xlsx"'

        return response

    # Unsupported format
    else:
        messages.error(request, f'Das Format "{export_format}" wird nicht unterstützt.')
        return redirect('import_log_list')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def get_user_permissions(request):
    """AJAX-Endpunkt zum Laden der Benutzerberechtigungen."""
    user_id = request.GET.get('user_id')

    try:
        user = User.objects.get(pk=user_id)

        # Gruppen
        groups = list(user.groups.values_list('id', flat=True))

        # Direkte Berechtigungen
        direct_permissions = list(user.user_permissions.values_list('id', flat=True))

        # Effektive Berechtigungen (inkl. Gruppen)
        effective_permissions = []

        # Aus Gruppen
        for group in user.groups.all():
            for perm in group.permissions.all():
                effective_permissions.append({
                    'id': perm.id,
                    'name': perm.name,
                    'codename': perm.codename,
                    'source': f'Gruppe: {group.name}'
                })

        # Direkte
        for perm in user.user_permissions.all():
            effective_permissions.append({
                'id': perm.id,
                'name': perm.name,
                'codename': perm.codename,
                'source': 'Direkt zugewiesen'
            })

        return JsonResponse({
            'groups': groups,
            'direct_permissions': direct_permissions,
            'effective_permissions': effective_permissions
        })

    except User.DoesNotExist:
        return JsonResponse({'error': 'Benutzer nicht gefunden'}, status=404)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def permission_management(request):
    """Verwaltung der Benutzerberechtigungen."""
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
                    messages.success(request, f'Benutzer {user.username} wurde zur Gruppe {group.name} hinzugefügt.')
                else:
                    user.groups.remove(group)
                    messages.success(request, f'Benutzer {user.username} wurde aus der Gruppe {group.name} entfernt.')

            except (User.DoesNotExist, Group.DoesNotExist):
                messages.error(request, "Benutzer oder Gruppe nicht gefunden.")

        elif action == 'direct_permission':
            user_id = request.POST.get('user_id')
            perm_id = request.POST.get('permission_id')

            try:
                user = User.objects.get(pk=user_id)
                perm = Permission.objects.get(pk=perm_id)

                if request.POST.get('assign') == 'true':
                    user.user_permissions.add(perm)
                    messages.success(request, f'Berechtigung {perm.name} wurde {user.username} direkt zugewiesen.')
                else:
                    user.user_permissions.remove(perm)
                    messages.success(request, f'Berechtigung {perm.name} wurde von {user.username} entfernt.')

            except (User.DoesNotExist, Permission.DoesNotExist):
                messages.error(request, "Benutzer oder Berechtigung nicht gefunden.")

    # Berechtigungen nach Bereichen gruppieren
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

    return render(request, 'core/permission_management.html', context)


# ------------------------------------------------------------------------------
# Produktfotos
# ------------------------------------------------------------------------------

@login_required
@permission_required('product', 'view')
def product_photos(request, pk):
    """Zeigt alle Fotos eines Produkts an."""
    product = get_object_or_404(Product, pk=pk)
    photos = product.photos.all()

    context = {
        'product': product,
        'photos': photos,
    }

    return render(request, 'core/product/product_photos.html', context)


@login_required
@permission_required('product', 'edit')
def product_photo_add(request, pk):
    """Fügt ein Foto zu einem Produkt hinzu."""
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductPhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.product = product
            photo.save()

            messages.success(request, 'Foto wurde erfolgreich hinzugefügt.')
            return redirect('product_photos', pk=product.pk)
    else:
        form = ProductPhotoForm()

    context = {
        'product': product,
        'form': form,
    }

    return render(request, 'core/product/product_photo_form.html', context)


@login_required
@permission_required('product', 'delete')
def product_photo_delete(request, pk, photo_id):
    """Löscht ein Produktfoto."""
    product = get_object_or_404(Product, pk=pk)
    photo = get_object_or_404(ProductPhoto, pk=photo_id, product=product)

    if request.method == 'POST':
        # Datei vom Dateisystem löschen
        if photo.image:
            if os.path.isfile(photo.image.path):
                os.remove(photo.image.path)

        photo.delete()
        messages.success(request, 'Foto wurde erfolgreich gelöscht.')
        return redirect('product_photos', pk=product.pk)

    context = {
        'product': product,
        'photo': photo,
    }

    return render(request, 'core/product/product_photo_confirm_delete.html', context)


@login_required
@permission_required('product', 'edit')
def product_photo_set_primary(request, pk, photo_id):
    """Setzt ein Foto als Hauptfoto des Produkts."""
    product = get_object_or_404(Product, pk=pk)
    photo = get_object_or_404(ProductPhoto, pk=photo_id, product=product)

    # Erst alle anderen Fotos als nicht-primär markieren
    ProductPhoto.objects.filter(product=product).update(is_primary=False)

    # Dann dieses Foto als primär markieren
    photo.is_primary = True
    photo.save()

    messages.success(request, 'Hauptfoto wurde erfolgreich gesetzt.')

    # AJAX-Request oder normale Anfrage unterscheiden
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    else:
        return redirect('product_photos', pk=product.pk)


# ------------------------------------------------------------------------------
# Produktanhänge
# ------------------------------------------------------------------------------

@login_required
@permission_required('product', 'view')
def product_attachments(request, pk):
    """Zeigt alle Anhänge eines Produkts an."""
    product = get_object_or_404(Product, pk=pk)
    attachments = product.attachments.all()

    context = {
        'product': product,
        'attachments': attachments,
    }

    return render(request, 'core/product/product_attachments.html', context)


@login_required
@permission_required('product', 'edit')
def product_attachment_add(request, pk):
    """Fügt einen Anhang zu einem Produkt hinzu."""
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.product = product
            attachment.save()

            messages.success(request, 'Anhang wurde erfolgreich hinzugefügt.')
            return redirect('product_attachments', pk=product.pk)
    else:
        form = ProductAttachmentForm()

    context = {
        'product': product,
        'form': form,
    }

    return render(request, 'core/product/product_attachment_form.html', context)


@login_required
@permission_required('product', 'delete')
def product_attachment_delete(request, pk, attachment_id):
    """Löscht einen Produktanhang."""
    product = get_object_or_404(Product, pk=pk)
    attachment = get_object_or_404(ProductAttachment, pk=attachment_id, product=product)

    if request.method == 'POST':
        # Datei vom Dateisystem löschen
        if attachment.file:
            if os.path.isfile(attachment.file.path):
                os.remove(attachment.file.path)

        attachment.delete()
        messages.success(request, 'Anhang wurde erfolgreich gelöscht.')
        return redirect('product_attachments', pk=product.pk)

    context = {
        'product': product,
        'attachment': attachment,
    }

    return render(request, 'core/product/product_attachment_confirm_delete.html', context)


@login_required
@permission_required('product', 'view')
def product_attachment_download(request, pk, attachment_id):
    """Lädt einen Produktanhang herunter."""
    product = get_object_or_404(Product, pk=pk)
    attachment = get_object_or_404(ProductAttachment, pk=attachment_id, product=product)

    if not attachment.file:
        raise Http404("Die angeforderte Datei existiert nicht.")

    file_path = attachment.file.path

    if not os.path.exists(file_path):
        raise Http404("Die angeforderte Datei existiert nicht.")

    # Mime-Type bestimmen
    content_type, encoding = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'application/octet-stream'

    # Datei öffnen und als Response senden
    try:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response
    except Exception as e:
        messages.error(request, f"Fehler beim Herunterladen der Datei: {str(e)}")
        return redirect('product_attachments', pk=product.pk)


# ------------------------------------------------------------------------------
# Variantentypen
# ------------------------------------------------------------------------------

@login_required
@permission_required('product', 'view')
def variant_type_list(request):
    """Zeigt alle Variantentypen an."""
    variant_types = ProductVariantType.objects.all()

    # Varianten pro Typ zählen
    variant_types_with_count = []
    for vt in variant_types:
        variant_count = ProductVariant.objects.filter(variant_type=vt).count()
        variant_types_with_count.append({
            'type': vt,
            'variant_count': variant_count
        })

    context = {
        'variant_types': variant_types_with_count,
    }

    return render(request, 'core/variant_type/variant_type_list.html', context)


@login_required
@permission_required('product', 'create')
def variant_type_add(request):
    """Erstellt einen neuen Variantentyp."""
    if request.method == 'POST':
        form = ProductVariantTypeForm(request.POST)
        if form.is_valid():
            variant_type = form.save()
            messages.success(request, f'Variantentyp "{variant_type.name}" wurde erfolgreich erstellt.')
            return redirect('variant_type_list')
    else:
        form = ProductVariantTypeForm()

    context = {
        'form': form,
    }

    return render(request, 'core/variant_type/variant_type_form.html', context)


@login_required
@permission_required('product', 'edit')
def variant_type_update(request, pk):
    """Aktualisiert einen Variantentyp."""
    variant_type = get_object_or_404(ProductVariantType, pk=pk)

    if request.method == 'POST':
        form = ProductVariantTypeForm(request.POST, instance=variant_type)
        if form.is_valid():
            variant_type = form.save()
            messages.success(request, f'Variantentyp "{variant_type.name}" wurde erfolgreich aktualisiert.')
            return redirect('variant_type_list')
    else:
        form = ProductVariantTypeForm(instance=variant_type)

    context = {
        'form': form,
        'variant_type': variant_type,
    }

    return render(request, 'core/variant_type/variant_type_form.html', context)


@login_required
@permission_required('product', 'delete')
def variant_type_delete(request, pk):
    """Löscht einen Variantentyp."""
    variant_type = get_object_or_404(ProductVariantType, pk=pk)

    # Prüfen, ob Varianten diesen Typ verwenden
    variant_count = ProductVariant.objects.filter(variant_type=variant_type).count()

    if request.method == 'POST':
        if variant_count > 0 and 'confirm_delete' not in request.POST:
            messages.error(request, f'Dieser Variantentyp wird von {variant_count} Varianten verwendet. '
                                    f'Löschen bestätigen, um trotzdem fortzufahren.')
            return redirect('variant_type_delete', pk=variant_type.pk)

        variant_type.delete()
        messages.success(request, f'Variantentyp "{variant_type.name}" wurde erfolgreich gelöscht.')
        return redirect('variant_type_list')

    context = {
        'variant_type': variant_type,
        'variant_count': variant_count,
    }

    return render(request, 'core/variant_type/variant_type_confirm_delete.html', context)


# ------------------------------------------------------------------------------
# Produktvarianten
# ------------------------------------------------------------------------------

@login_required
@permission_required('product', 'view')
def product_variants(request, pk):
    """Zeigt alle Varianten eines Produkts an."""
    product = get_object_or_404(Product, pk=pk)
    variants = product.variants.all()

    context = {
        'product': product,
        'variants': variants,
    }

    return render(request, 'core/product/product_variants.html', context)


@login_required
@permission_required('product', 'view')
def product_variant_detail(request, pk, variant_id):
    """Zeigt Details zu einer Produktvariante an."""
    product = get_object_or_404(Product, pk=pk)
    variant = get_object_or_404(ProductVariant, pk=variant_id, parent_product=product)

    # Seriennummern für diese Variante
    serial_numbers = SerialNumber.objects.filter(variant=variant)

    # Chargen für diese Variante
    batches = BatchNumber.objects.filter(variant=variant)

    context = {
        'product': product,
        'variant': variant,
        'serial_numbers': serial_numbers,
        'batches': batches,
    }

    return render(request, 'core/product/product_variant_detail.html', context)


@login_required
@permission_required('product', 'create')
def product_variant_add(request, pk):
    """Fügt eine Variante zu einem Produkt hinzu."""
    product = get_object_or_404(Product, pk=pk)

    # Prüfen, ob das Produkt für Varianten konfiguriert ist
    if not product.has_variants:
        product.has_variants = True
        product.save()
        messages.info(request, 'Das Produkt wurde für Varianten aktiviert.')

    if request.method == 'POST':
        form = ProductVariantForm(request.POST)
        if form.is_valid():
            variant = form.save(commit=False)
            variant.parent_product = product
            variant.save()

            messages.success(request, 'Produktvariante wurde erfolgreich hinzugefügt.')
            return redirect('product_variants', pk=product.pk)
    else:
        # Name-Vorschlag generieren
        form = ProductVariantForm(initial={
            'name': product.name,
            'current_stock': 0
        })

    context = {
        'product': product,
        'form': form,
    }

    return render(request, 'core/product/product_variant_form.html', context)


@login_required
@permission_required('product', 'edit')
def product_variant_update(request, pk, variant_id):
    """Aktualisiert eine Produktvariante."""
    product = get_object_or_404(Product, pk=pk)
    variant = get_object_or_404(ProductVariant, pk=variant_id, parent_product=product)

    if request.method == 'POST':
        form = ProductVariantForm(request.POST, instance=variant)
        if form.is_valid():
            variant = form.save()
            messages.success(request, 'Produktvariante wurde erfolgreich aktualisiert.')
            return redirect('product_variants', pk=product.pk)
    else:
        form = ProductVariantForm(instance=variant)

    context = {
        'product': product,
        'variant': variant,
        'form': form,
    }

    return render(request, 'core/product/product_variant_form.html', context)


@login_required
@permission_required('product', 'delete')
def product_variant_delete(request, pk, variant_id):
    """Löscht eine Produktvariante."""
    product = get_object_or_404(Product, pk=pk)
    variant = get_object_or_404(ProductVariant, pk=variant_id, parent_product=product)

    if request.method == 'POST':
        variant.delete()
        messages.success(request, 'Produktvariante wurde erfolgreich gelöscht.')

        # Wenn keine Varianten mehr übrig sind, has_variants zurücksetzen
        if not product.variants.exists():
            product.has_variants = False
            product.save()

        return redirect('product_variants', pk=product.pk)

    context = {
        'product': product,
        'variant': variant,
    }

    return render(request, 'core/product/product_variant_confirm_delete.html', context)


# ------------------------------------------------------------------------------
# Seriennummern
# ------------------------------------------------------------------------------

@login_required
@permission_required('product', 'view')
def product_serials(request, pk):
    """Zeigt alle Seriennummern eines Produkts an."""
    product = get_object_or_404(Product, pk=pk)

    # Filteroptionen
    status_filter = request.GET.get('status', '')
    warehouse_filter = request.GET.get('warehouse', '')
    variant_filter = request.GET.get('variant', '')
    search_query = request.GET.get('search', '')

    serials = SerialNumber.objects.filter(product=product)

    if status_filter:
        serials = serials.filter(status=status_filter)

    if warehouse_filter:
        serials = serials.filter(warehouse_id=warehouse_filter)

    if variant_filter:
        serials = serials.filter(variant_id=variant_filter)

    if search_query:
        serials = serials.filter(serial_number__icontains=search_query)

    # Paginierung
    paginator = Paginator(serials, 50)  # 50 Seriennummern pro Seite
    page = request.GET.get('page')
    try:
        serials = paginator.page(page)
    except PageNotAnInteger:
        serials = paginator.page(1)
    except EmptyPage:
        serials = paginator.page(paginator.num_pages)

    # Status-Statistiken
    status_counts = SerialNumber.objects.filter(product=product).values('status').annotate(
        count=Count('status')).order_by('status')

    # In Dictionary umwandeln für leichteren Zugriff
    status_stats = {item['status']: item['count'] for item in status_counts}

    context = {
        'product': product,
        'serials': serials,
        'status_stats': status_stats,
        'warehouses': Warehouse.objects.filter(is_active=True),
        'variants': product.variants.all(),
        'status_choices': SerialNumber.status_choices,
        'status_filter': status_filter,
        'warehouse_filter': warehouse_filter,
        'variant_filter': variant_filter,
        'search_query': search_query,
    }

    return render(request, 'core/product/product_serials.html', context)


@login_required
@permission_required('product', 'create')
def product_serial_add(request, pk):
    """Fügt eine Seriennummer zu einem Produkt hinzu."""
    product = get_object_or_404(Product, pk=pk)

    # Prüfen, ob das Produkt für Seriennummern konfiguriert ist
    if not product.has_serial_numbers:
        product.has_serial_numbers = True
        product.save()
        messages.info(request, 'Das Produkt wurde für Seriennummern aktiviert.')

    if request.method == 'POST':
        form = SerialNumberForm(request.POST, product=product)
        if form.is_valid():
            serial = form.save(commit=False)
            serial.product = product
            serial.save()

            messages.success(request, 'Seriennummer wurde erfolgreich hinzugefügt.')
            return redirect('product_serials', pk=product.pk)
    else:
        form = SerialNumberForm(product=product)

    context = {
        'product': product,
        'form': form,
    }

    return render(request, 'core/product/product_serial_form.html', context)


@login_required
@permission_required('product', 'create')
def product_serial_bulk_add(request, pk):
    """Fügt mehrere Seriennummern zu einem Produkt hinzu."""
    product = get_object_or_404(Product, pk=pk)

    # Prüfen, ob das Produkt für Seriennummern konfiguriert ist
    if not product.has_serial_numbers:
        product.has_serial_numbers = True
        product.save()
        messages.info(request, 'Das Produkt wurde für Seriennummern aktiviert.')

    if request.method == 'POST':
        form = BulkSerialNumberForm(request.POST, product=product)
        if form.is_valid():
            prefix = form.cleaned_data.get('prefix', '')
            start_number = form.cleaned_data.get('start_number')
            count = form.cleaned_data.get('count')
            digits = form.cleaned_data.get('digits')
            status = form.cleaned_data.get('status')
            warehouse = form.cleaned_data.get('warehouse')
            purchase_date = form.cleaned_data.get('purchase_date')
            expiry_date = form.cleaned_data.get('expiry_date')
            variant = form.cleaned_data.get('variant')

            # Format für Seriennummern erstellen
            serial_format = f"{prefix}{{:0{digits}d}}"

            # Prüfen, ob Seriennummern bereits existieren
            existing_numbers = []
            for i in range(start_number, start_number + count):
                serial_number = serial_format.format(i)
                if SerialNumber.objects.filter(serial_number=serial_number).exists():
                    existing_numbers.append(serial_number)

            if existing_numbers:
                messages.error(request,
                               f'Folgende Seriennummern existieren bereits: {", ".join(existing_numbers[:10])}' +
                               (f' und {len(existing_numbers) - 10} weitere' if len(existing_numbers) > 10 else ''))
                context = {
                    'product': product,
                    'form': form,
                }
                return render(request, 'core/product/product_serial_bulk_form.html', context)

            # Seriennummern erstellen
            created_count = 0
            for i in range(start_number, start_number + count):
                serial_number = serial_format.format(i)
                SerialNumber.objects.create(
                    product=product,
                    serial_number=serial_number,
                    status=status,
                    warehouse=warehouse,
                    purchase_date=purchase_date,
                    expiry_date=expiry_date,
                    variant=variant
                )
                created_count += 1

            messages.success(request, f'{created_count} Seriennummern wurden erfolgreich erstellt.')
            return redirect('product_serials', pk=product.pk)
    else:
        form = BulkSerialNumberForm(product=product)

    context = {
        'product': product,
        'form': form,
    }

    return render(request, 'core/product/product_serial_bulk_form.html', context)


@login_required
@permission_required('product', 'edit')
def product_serial_update(request, pk, serial_id):
    """Aktualisiert eine Seriennummer."""
    product = get_object_or_404(Product, pk=pk)
    serial = get_object_or_404(SerialNumber, pk=serial_id, product=product)

    if request.method == 'POST':
        form = SerialNumberForm(request.POST, instance=serial, product=product)
        if form.is_valid():
            serial = form.save()
            messages.success(request, 'Seriennummer wurde erfolgreich aktualisiert.')
            return redirect('product_serials', pk=product.pk)
    else:
        form = SerialNumberForm(instance=serial, product=product)

    context = {
        'product': product,
        'serial': serial,
        'form': form,
    }

    return render(request, 'core/product/product_serial_form.html', context)


@login_required
@permission_required('product', 'delete')
def product_serial_delete(request, pk, serial_id):
    """Löscht eine Seriennummer."""
    product = get_object_or_404(Product, pk=pk)
    serial = get_object_or_404(SerialNumber, pk=serial_id, product=product)

    if request.method == 'POST':
        serial.delete()
        messages.success(request, 'Seriennummer wurde erfolgreich gelöscht.')
        return redirect('product_serials', pk=product.pk)

    context = {
        'product': product,
        'serial': serial,
    }

    return render(request, 'core/product/product_serial_confirm_delete.html', context)


# ------------------------------------------------------------------------------
# Chargen
# ------------------------------------------------------------------------------

@login_required
@permission_required('product', 'view')
def product_batches(request, pk):
    """Zeigt alle Chargen eines Produkts an."""
    product = get_object_or_404(Product, pk=pk)

    # Filteroptionen
    warehouse_filter = request.GET.get('warehouse', '')
    variant_filter = request.GET.get('variant', '')
    search_query = request.GET.get('search', '')
    expiry_filter = request.GET.get('expiry', '')

    batches = BatchNumber.objects.filter(product=product)

    if warehouse_filter:
        batches = batches.filter(warehouse_id=warehouse_filter)

    if variant_filter:
        batches = batches.filter(variant_id=variant_filter)

    if search_query:
        batches = batches.filter(batch_number__icontains=search_query)

    # Filtern nach Verfallsdatum
    today = timezone.now().date()
    if expiry_filter == 'expired':
        batches = batches.filter(expiry_date__lt=today)
    elif expiry_filter == 'expiring_soon':
        batches = batches.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30))
    elif expiry_filter == 'valid':
        batches = batches.filter(expiry_date__gt=today + timedelta(days=30))

    # Paginierung
    paginator = Paginator(batches, 25)  # 25 Chargen pro Seite
    page = request.GET.get('page')
    try:
        batches = paginator.page(page)
    except PageNotAnInteger:
        batches = paginator.page(1)
    except EmptyPage:
        batches = paginator.page(paginator.num_pages)

    # Verfallsstatistiken
    expired_count = BatchNumber.objects.filter(product=product, expiry_date__lt=today).count()
    expiring_soon_count = BatchNumber.objects.filter(
        product=product,
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=30)
    ).count()
    valid_count = BatchNumber.objects.filter(
        product=product,
        expiry_date__gt=today + timedelta(days=30)
    ).count()

    context = {
        'product': product,
        'batches': batches,
        'warehouses': Warehouse.objects.filter(is_active=True),
        'variants': product.variants.all(),
        'warehouse_filter': warehouse_filter,
        'variant_filter': variant_filter,
        'search_query': search_query,
        'expiry_filter': expiry_filter,
        'expired_count': expired_count,
        'expiring_soon_count': expiring_soon_count,
        'valid_count': valid_count,
        'today': today,
    }

    return render(request, 'core/product/product_batches.html', context)


@login_required
@permission_required('product', 'create')
def product_batch_add(request, pk):
    """Fügt eine Charge zu einem Produkt hinzu."""
    product = get_object_or_404(Product, pk=pk)

    # Prüfen, ob das Produkt für Chargen konfiguriert ist
    if not product.has_batch_tracking:
        product.has_batch_tracking = True
        product.save()
        messages.info(request, 'Das Produkt wurde für Chargenverfolgung aktiviert.')

    if request.method == 'POST':
        form = BatchNumberForm(request.POST, product=product)
        if form.is_valid():
            batch = form.save(commit=False)
            batch.product = product
            batch.save()

            messages.success(request, 'Charge wurde erfolgreich hinzugefügt.')
            return redirect('product_batches', pk=product.pk)
    else:
        form = BatchNumberForm(product=product)

    context = {
        'product': product,
        'form': form,
    }

    return render(request, 'core/product/product_batch_form.html', context)


@login_required
@permission_required('product', 'edit')
def product_batch_update(request, pk, batch_id):
    """Aktualisiert eine Charge."""
    product = get_object_or_404(Product, pk=pk)
    batch = get_object_or_404(BatchNumber, pk=batch_id, product=product)

    if request.method == 'POST':
        form = BatchNumberForm(request.POST, instance=batch, product=product)
        if form.is_valid():
            batch = form.save()
            messages.success(request, 'Charge wurde erfolgreich aktualisiert.')
            return redirect('product_batches', pk=product.pk)
    else:
        form = BatchNumberForm(instance=batch, product=product)

    context = {
        'product': product,
        'batch': batch,
        'form': form,
    }

    return render(request, 'core/product/product_batch_form.html', context)


@login_required
@permission_required('product', 'delete')
def product_batch_delete(request, pk, batch_id):
    """Löscht eine Charge."""
    product = get_object_or_404(Product, pk=pk)
    batch = get_object_or_404(BatchNumber, pk=batch_id, product=product)

    if request.method == 'POST':
        batch.delete()
        messages.success(request, 'Charge wurde erfolgreich gelöscht.')
        return redirect('product_batches', pk=product.pk)

    context = {
        'product': product,
        'batch': batch,
    }

    return render(request, 'core/product/product_batch_confirm_delete.html', context)


# ------------------------------------------------------------------------------
# Verfallsdaten-Verwaltung
# ------------------------------------------------------------------------------

@login_required
@permission_required('product', 'view')
def expiry_management(request):
    """Zentrale Verwaltung aller Produkte mit Verfallsdaten."""
    # Filteroptionen
    expiry_filter = request.GET.get('filter', 'all')
    days_threshold = request.GET.get('days_threshold', '30')
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')

    try:
        days_threshold = int(days_threshold)
    except ValueError:
        days_threshold = 30

    today = timezone.now().date()

    # Basis-Queryset für Seriennummern mit Verfallsdaten
    serials = SerialNumber.objects.filter(expiry_date__isnull=False)

    # Basis-Queryset für Chargen mit Verfallsdaten
    batches = BatchNumber.objects.filter(expiry_date__isnull=False)

    # Filterung nach Ablaufstatus
    if expiry_filter == 'expired':
        serials = serials.filter(expiry_date__lt=today)
        batches = batches.filter(expiry_date__lt=today)
    elif expiry_filter == 'expiring_soon':
        serials = serials.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=days_threshold)
        )
        batches = batches.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=days_threshold)
        )
    elif expiry_filter == 'valid':
        serials = serials.filter(expiry_date__gt=today + timedelta(days=days_threshold))
        batches = batches.filter(expiry_date__gt=today + timedelta(days=days_threshold))

    # Filterung nach Suchbegriff
    if search_query:
        serials = serials.filter(
            Q(product__name__icontains=search_query) |
            Q(serial_number__icontains=search_query)
        )
        batches = batches.filter(
            Q(product__name__icontains=search_query) |
            Q(batch_number__icontains=search_query)
        )

    # Filterung nach Kategorie
    if category_filter:
        serials = serials.filter(product__category_id=category_filter)
        batches = batches.filter(product__category_id=category_filter)

    # Statistiken für Seriennummern
    serial_stats = {
        'total': SerialNumber.objects.filter(expiry_date__isnull=False).count(),
        'expired': SerialNumber.objects.filter(expiry_date__lt=today).count(),
        'expiring_soon': SerialNumber.objects.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=days_threshold)
        ).count(),
        'valid': SerialNumber.objects.filter(
            expiry_date__gt=today + timedelta(days=days_threshold)
        ).count(),
    }

    # Statistiken für Chargen
    batch_stats = {
        'total': BatchNumber.objects.filter(expiry_date__isnull=False).count(),
        'expired': BatchNumber.objects.filter(expiry_date__lt=today).count(),
        'expiring_soon': BatchNumber.objects.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=days_threshold)
        ).count(),
        'valid': BatchNumber.objects.filter(
            expiry_date__gt=today + timedelta(days=days_threshold)
        ).count(),
    }

    # Paginierung für Seriennummern
    serials_paginator = Paginator(serials, 25)
    serials_page = request.GET.get('serials_page')
    try:
        serials = serials_paginator.page(serials_page)
    except PageNotAnInteger:
        serials = serials_paginator.page(1)
    except EmptyPage:
        serials = serials_paginator.page(serials_paginator.num_pages)

    # Paginierung für Chargen
    batches_paginator = Paginator(batches, 25)
    batches_page = request.GET.get('batches_page')
    try:
        batches = batches_paginator.page(batches_page)
    except PageNotAnInteger:
        batches = batches_paginator.page(1)
    except EmptyPage:
        batches = batches_paginator.page(batches_paginator.num_pages)

    context = {
        'serials': serials,
        'batches': batches,
        'serial_stats': serial_stats,
        'batch_stats': batch_stats,
        'categories': Category.objects.all(),
        'expiry_filter': expiry_filter,
        'days_threshold': days_threshold,
        'search_query': search_query,
        'category_filter': category_filter,
        'today': today,
    }

    return render(request, 'core/expiry_management.html', context)


# ------------------------------------------------------------------------------
# Erweiterung der bestehenden Produkt-Views
# ------------------------------------------------------------------------------

# Aktualisieren der product_detail View, um die erweiterten Funktionen anzuzeigen
@login_required
@permission_required('product', 'view')
def product_detail(request, pk):
    """Show details for a specific product."""
    product = get_object_or_404(Product, pk=pk)

    # Lieferanteninformationen
    supplier_products = SupplierProduct.objects.filter(product=product).select_related('supplier')

    # Bestandsbewegungen
    movements = StockMovement.objects.filter(product=product).select_related('created_by').order_by('-created_at')[:20]

    # Primärbild abrufen, falls vorhanden
    primary_photo = product.photos.filter(is_primary=True).first()

    # Anzahl der Varianten, Seriennummern und Chargen
    variant_count = product.variants.count()
    serial_count = product.serial_numbers.count()
    batch_count = product.batches.count()

    # Varianten mit kritischem Bestand
    low_stock_variants = product.variants.filter(
        current_stock__lt=3  # Beispielwert als Schwellenwert
    )[:5]  # Nur die ersten 5 anzeigen

    # Ablaufende Seriennummern und Chargen
    today = timezone.now().date()
    expiring_serials = product.serial_numbers.filter(
        expiry_date__isnull=False,
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=30)
    ).order_by('expiry_date')[:5]

    expiring_batches = product.batches.filter(
        expiry_date__isnull=False,
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=30)
    ).order_by('expiry_date')[:5]

    # Seriennummern nach Status gruppieren
    serial_status_counts = {}
    if product.has_serial_numbers:
        status_choices = SerialNumber.status_choices
        for status_code, status_name in status_choices:
            serial_status_counts[status_code] = product.serial_numbers.filter(status=status_code).count()

    context = {
        'product': product,
        'supplier_products': supplier_products,
        'movements': movements,
        'primary_photo': primary_photo,
        'variant_count': variant_count,
        'serial_count': serial_count,
        'batch_count': batch_count,
        'low_stock_variants': low_stock_variants,
        'expiring_serials': expiring_serials,
        'expiring_batches': expiring_batches,
        'serial_status_counts': serial_status_counts,  # Neue Variable für die Seriennummern-Statistik
    }

    return render(request, 'core/product_detail.html', context)


# ------------------------------------------------------------------------------
# Globale Seriennummern-Verwaltung
# ------------------------------------------------------------------------------

@login_required
@permission_required('serialnumber', 'view')
def serialnumber_list(request):
    """Zeigt alle Seriennummern im System an."""
    # Filteroptionen
    status_filter = request.GET.get('status', '')
    warehouse_filter = request.GET.get('warehouse', '')
    product_filter = request.GET.get('product', '')
    search_query = request.GET.get('search', '')

    serials = SerialNumber.objects.select_related('product', 'warehouse', 'variant')

    if status_filter:
        serials = serials.filter(status=status_filter)

    if warehouse_filter:
        serials = serials.filter(warehouse_id=warehouse_filter)

    if product_filter:
        serials = serials.filter(product_id=product_filter)

    if search_query:
        serials = serials.filter(
            Q(serial_number__icontains=search_query) |
            Q(product__name__icontains=search_query) |
            Q(variant__name__icontains=search_query)
        )

    # Sortierung
    sort_by = request.GET.get('sort', '-created_at')
    serials = serials.order_by(sort_by)

    # Paginierung
    paginator = Paginator(serials, 50)  # 50 Seriennummern pro Seite
    page = request.GET.get('page')
    try:
        serials = paginator.page(page)
    except PageNotAnInteger:
        serials = paginator.page(1)
    except EmptyPage:
        serials = paginator.page(paginator.num_pages)

    # Status-Statistiken
    status_counts = SerialNumber.objects.values('status').annotate(
        count=Count('status')).order_by('status')

    # In Dictionary umwandeln für leichteren Zugriff
    status_stats = {item['status']: item['count'] for item in status_counts}

    context = {
        'serials': serials,
        'status_stats': status_stats,
        'warehouses': Warehouse.objects.filter(is_active=True),
        'products': Product.objects.filter(has_serial_numbers=True),
        'status_choices': SerialNumber.status_choices,
        'status_filter': status_filter,
        'warehouse_filter': warehouse_filter,
        'product_filter': product_filter,
        'search_query': search_query,
        'sort_by': sort_by,
    }

    return render(request, 'core/serialnumber/serialnumber_list.html', context)


@login_required
@permission_required('serialnumber', 'view')
def serialnumber_detail(request, serial_id):
    """Zeigt Details zu einer Seriennummer an."""
    serial = get_object_or_404(SerialNumber.objects.select_related(
        'product', 'warehouse', 'variant'), pk=serial_id)

    # Hier könnten später Bewegungshistorie, Wartungsprotokolle etc. geladen werden

    context = {
        'serial': serial,
    }

    return render(request, 'core/serialnumber/serialnumber_detail.html', context)


@login_required
@permission_required('serialnumber', 'view')
def serialnumber_history(request, serial_id):
    """Zeigt die Historie einer Seriennummer an."""
    serial = get_object_or_404(SerialNumber.objects.select_related(
        'product', 'warehouse', 'variant'), pk=serial_id)

    # Hier würde man die Historiendaten laden
    # Beispiel: movements = SerialNumberMovement.objects.filter(serial_number=serial).order_by('-timestamp')

    context = {
        'serial': serial,
        'movements': [],  # Platzhalter für die tatsächlichen Bewegungsdaten
    }

    return render(request, 'core/serialnumber/serialnumber_history.html', context)


@login_required
@permission_required('serialnumber', 'add')
def serialnumber_add(request):
    """Fügt eine neue Seriennummer hinzu (produktunabhängig)."""
    if request.method == 'POST':
        form = SerialNumberForm(request.POST)
        if form.is_valid():
            serial = form.save()

            # Produkt für Seriennummern aktivieren, falls noch nicht geschehen
            product = serial.product
            if not product.has_serial_numbers:
                product.has_serial_numbers = True
                product.save()

            messages.success(request, 'Seriennummer wurde erfolgreich hinzugefügt.')
            return redirect('serialnumber_list')
    else:
        form = SerialNumberForm()

    context = {
        'form': form,
    }

    return render(request, 'core/serialnumber/serialnumber_form.html', context)


@login_required
@permission_required('serialnumber', 'transfer')
def serialnumber_transfer(request):
    """Transferiert eine Seriennummer von einem Lager zu einem anderen."""
    if request.method == 'POST':
        serial_number = request.POST.get('serial_number')
        target_warehouse_id = request.POST.get('target_warehouse')

        try:
            serial = SerialNumber.objects.get(serial_number=serial_number)
            old_warehouse = serial.warehouse
            new_warehouse = Warehouse.objects.get(pk=target_warehouse_id)

            # Prüfe Benutzerberechtigungen für beide Lager
            if not request.user.is_superuser:
                if (old_warehouse and not WarehouseAccess.has_access(request.user, old_warehouse)) or \
                        not WarehouseAccess.has_access(request.user, new_warehouse):
                    messages.error(request, 'Sie haben keine Berechtigung für eines der Lager.')
                    return redirect('serialnumber_transfer')

            # Formatierte Meldung erstellen, je nachdem ob ein altes Lager vorhanden war
            if old_warehouse:
                success_message = f'Seriennummer {serial_number} wurde erfolgreich von ' \
                                  f'{old_warehouse.name} nach {new_warehouse.name} transferiert.'
            else:
                success_message = f'Seriennummer {serial_number} wurde erfolgreich ' \
                                  f'dem Lager {new_warehouse.name} zugewiesen.'

            # Speichere den Transfer
            serial.warehouse = new_warehouse
            serial.last_modified = timezone.now()
            serial.save()

            # Hier könnte man auch einen Eintrag in einer Transfer-Historie speichern

            messages.success(request, success_message)
            return redirect('serialnumber_list')

        except SerialNumber.DoesNotExist:
            messages.error(request, f'Seriennummer {serial_number} wurde nicht gefunden.')
        except Warehouse.DoesNotExist:
            messages.error(request, 'Das Ziellager existiert nicht.')
        except Exception as e:
            messages.error(request, f'Fehler beim Transferieren: {str(e)}')

    # Für GET-Anfragen oder bei Fehlern im POST
    warehouses = Warehouse.objects.filter(is_active=True)

    # Wenn eine Seriennummer als Parameter übergeben wurde (z.B. aus der Detailansicht)
    initial_serial = request.GET.get('serial', '')

    context = {
        'warehouses': warehouses,
        'initial_serial': initial_serial,
    }

    return render(request, 'core/serialnumber/serialnumber_transfer.html', context)


@login_required
@permission_required('serialnumber', 'import')
def serialnumber_import(request):
    """Importiert Seriennummern aus einer CSV-Datei."""
    if request.method == 'POST':
        # Hier würde der eigentliche Import-Code stehen
        # Ähnlich wie bei anderen Import-Funktionen des Systems

        # Beispiel für den Rückgabewert nach erfolgreichem Import
        messages.success(request, 'Seriennummern wurden erfolgreich importiert.')
        return redirect('serialnumber_list')

    context = {
        'title': 'Seriennummern importieren',
        'description': 'Importieren Sie Seriennummern aus einer CSV-Datei.',
        'expected_format': 'product_sku,serial_number,status,warehouse_name,purchase_date,expiry_date',
        'example': 'P1001,SN12345,in_stock,Hauptlager,2023-01-01,2025-01-01',
        'required_columns': ['product_sku', 'serial_number'],
        'optional_columns': ['status', 'warehouse_name', 'purchase_date', 'expiry_date', 'notes'],
    }

    return render(request, 'core/serialnumber/serialnumber_import.html', context)


@login_required
@permission_required('serialnumber', 'export')
def serialnumber_export(request):
    """Exportiert Seriennummern in eine CSV- oder Excel-Datei."""
    # Filteroptionen für den Export
    status_filter = request.GET.get('status', '')
    warehouse_filter = request.GET.get('warehouse', '')
    product_filter = request.GET.get('product', '')

    serials = SerialNumber.objects.select_related('product', 'warehouse', 'variant')

    if status_filter:
        serials = serials.filter(status=status_filter)

    if warehouse_filter:
        serials = serials.filter(warehouse_id=warehouse_filter)

    if product_filter:
        serials = serials.filter(product_id=product_filter)

    # Export-Format bestimmen
    export_format = request.GET.get('format', '')

    if export_format == 'csv':
        # CSV-Export
        response = HttpResponse(content_type='text/csv')
        response[
            'Content-Disposition'] = f'attachment; filename="seriennummern_{timezone.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Seriennummer', 'Produkt', 'Variante', 'Status', 'Lager',
            'Kaufdatum', 'Ablaufdatum', 'Notizen', 'Erstellt am'
        ])

        for serial in serials:
            writer.writerow([
                serial.serial_number,
                serial.product.name,
                serial.variant.name if serial.variant else '',
                serial.get_status_display(),
                serial.warehouse.name if serial.warehouse else '',
                serial.purchase_date.strftime('%Y-%m-%d') if serial.purchase_date else '',
                serial.expiry_date.strftime('%Y-%m-%d') if serial.expiry_date else '',
                serial.notes,
                serial.created_at.strftime('%Y-%m-%d %H:%M')
            ])

        return response

    elif export_format == 'excel':
        # Excel-Export würde hier implementiert werden
        # Ähnlich wie bei der export_import_logs-Funktion
        messages.error(request, 'Excel-Export ist derzeit nicht verfügbar.')
        return redirect('serialnumber_list')

    # Wenn kein Export angefordert wurde, zeige Exportformular
    context = {
        'warehouses': Warehouse.objects.filter(is_active=True),
        'products': Product.objects.filter(has_serial_numbers=True),
        'status_choices': SerialNumber.status_choices,
    }

    return render(request, 'core/serialnumber/serialnumber_export.html', context)


@login_required
@permission_required('serialnumber', 'view')
def serialnumber_scan(request):
    """Scannt eine Seriennummer (z.B. mit Barcode-Scanner) und zeigt Details an."""
    scanned_number = request.GET.get('scan', '')

    if scanned_number:
        try:
            serial = SerialNumber.objects.get(serial_number=scanned_number)
            # Weiterleitung zur Detailseite
            return redirect('serialnumber_detail', serial_id=serial.pk)
        except SerialNumber.DoesNotExist:
            messages.error(request, f'Seriennummer {scanned_number} wurde nicht gefunden.')

    context = {
        'scanned_number': scanned_number,
    }

    return render(request, 'core/serialnumber/serialnumber_scan.html', context)


@login_required
@permission_required('serialnumber', 'view')
def serialnumber_search(request):
    """Erweiterte Suchfunktion für Seriennummern."""
    search_query = request.GET.get('q', '')

    results = []
    if search_query:
        # Suche nach Seriennummer, Produktname, verschiedenen Feldern
        results = SerialNumber.objects.filter(
            Q(serial_number__icontains=search_query) |
            Q(product__name__icontains=search_query) |
            Q(product__sku__icontains=search_query) |
            Q(product__barcode__icontains=search_query) |
            Q(variant__name__icontains=search_query) |
            Q(notes__icontains=search_query)
        ).select_related('product', 'warehouse', 'variant')

    context = {
        'search_query': search_query,
        'results': results,
    }

    return render(request, 'core/serialnumber/serialnumber_search.html', context)


@login_required
@permission_required('serialnumber', 'edit')
def serialnumber_batch_actions(request):
    """Massenaktionen für mehrere Seriennummern gleichzeitig."""
    if request.method == 'POST':
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_serials')

        if not selected_ids:
            messages.error(request, 'Keine Seriennummern ausgewählt.')
            return redirect('serialnumber_list')

        # Seriennummern abrufen
        serials = SerialNumber.objects.filter(pk__in=selected_ids)

        if action == 'change_status':
            new_status = request.POST.get('new_status')
            if new_status:
                serials.update(status=new_status)
                messages.success(request,
                                 f'{len(selected_ids)} Seriennummern auf Status "{dict(SerialNumber.status_choices)[new_status]}" gesetzt.')

        elif action == 'change_warehouse':
            new_warehouse_id = request.POST.get('new_warehouse')
            if new_warehouse_id:
                try:
                    warehouse = Warehouse.objects.get(pk=new_warehouse_id)
                    serials.update(warehouse=warehouse)
                    messages.success(request, f'{len(selected_ids)} Seriennummern nach "{warehouse.name}" verschoben.')
                except Warehouse.DoesNotExist:
                    messages.error(request, 'Das ausgewählte Lager existiert nicht.')

        elif action == 'delete':
            count = serials.count()
            serials.delete()
            messages.success(request, f'{count} Seriennummern wurden gelöscht.')

        return redirect('serialnumber_list')

    # Standardwerte für GET-Anfrage
    context = {
        'status_choices': SerialNumber.status_choices,
        'warehouses': Warehouse.objects.filter(is_active=True),
    }

    return render(request, 'core/serialnumber/serialnumber_batch_actions.html', context)


@login_required
@permission_required('serialnumber', 'import')
def import_serialnumbers(request):
    """Importiert Seriennummern aus einer CSV-Datei."""
    if request.method == 'POST':
        form = request.POST
        csv_file = request.FILES.get('csv_file')

        if not csv_file:
            messages.error(request, 'Bitte wählen Sie eine CSV-Datei aus.')
            return redirect('import_serialnumbers')

        # Überprüfen des Dateityps
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Bitte laden Sie eine CSV-Datei hoch.')
            return redirect('import_serialnumbers')

        # Datei in Speicher lesen
        file_data = csv_file.read().decode('utf-8')

        # Import-Log erstellen
        import_log = ImportLog.objects.create(
            file_name=csv_file.name,
            import_type='serialnumbers',
            started_by=request.user,
            status='processing'
        )

        try:
            lines = file_data.split('\n')
            # CSV-Header überprüfen
            header = lines[0].strip().split(',')
            required_headers = ['product_sku', 'serial_number']
            optional_headers = ['status', 'warehouse_name', 'purchase_date', 'expiry_date', 'variant_name', 'notes']

            # Prüfen, ob alle erforderlichen Header vorhanden sind
            if not all(column in header for column in required_headers):
                import_log.status = 'failed'
                import_log.notes = f'Ungültiger CSV-Header. Erforderliche Felder: {", ".join(required_headers)}'
                import_log.save()
                messages.error(request, import_log.notes)
                return redirect('import_serialnumbers')

            # Indizes für die Spalten ermitteln
            product_sku_idx = header.index('product_sku')
            serial_number_idx = header.index('serial_number')

            # Optionale Felder
            status_idx = header.index('status') if 'status' in header else None
            warehouse_name_idx = header.index('warehouse_name') if 'warehouse_name' in header else None
            purchase_date_idx = header.index('purchase_date') if 'purchase_date' in header else None
            expiry_date_idx = header.index('expiry_date') if 'expiry_date' in header else None
            variant_name_idx = header.index('variant_name') if 'variant_name' in header else None
            notes_idx = header.index('notes') if 'notes' in header else None

            # Import starten
            created_count = 0
            updated_count = 0
            error_count = 0
            error_msgs = []

            # Update-Modus ermitteln
            update_existing = form.get('update_existing', 'False') == 'True'
            default_status = form.get('default_status', 'in_stock')
            default_warehouse_id = form.get('default_warehouse', None)

            # Standard-Lager ermitteln, falls angegeben
            default_warehouse = None
            if default_warehouse_id:
                try:
                    default_warehouse = Warehouse.objects.get(pk=default_warehouse_id)
                except Warehouse.DoesNotExist:
                    pass

            # CSV-Zeilen verarbeiten (ohne Header)
            for i, line in enumerate(lines[1:], 1):
                if not line.strip():  # Leere Zeile überspringen
                    continue

                try:
                    # Zeile parsen
                    fields = line.strip().split(',')

                    product_sku = fields[product_sku_idx].strip()
                    serial_number = fields[serial_number_idx].strip()

                    # Produkt finden
                    try:
                        product = Product.objects.get(sku=product_sku)
                    except Product.DoesNotExist:
                        error_count += 1
                        error_msg = f'Fehler in Zeile {i + 1}: Produkt mit SKU "{product_sku}" nicht gefunden.'
                        error_msgs.append(error_msg)
                        continue

                    # Prüfen, ob Seriennummer bereits existiert
                    existing_serial = SerialNumber.objects.filter(serial_number=serial_number).first()
                    if existing_serial and not update_existing:
                        error_count += 1
                        error_msg = f'Fehler in Zeile {i + 1}: Seriennummer "{serial_number}" existiert bereits.'
                        error_msgs.append(error_msg)
                        continue

                    # Optionale Felder extrahieren
                    status = fields[status_idx].strip() if status_idx is not None and status_idx < len(
                        fields) else default_status

                    # Lager finden, falls angegeben
                    warehouse = default_warehouse
                    if warehouse_name_idx is not None and warehouse_name_idx < len(fields) and fields[
                        warehouse_name_idx].strip():
                        warehouse_name = fields[warehouse_name_idx].strip()
                        try:
                            warehouse = Warehouse.objects.get(name=warehouse_name)
                        except Warehouse.DoesNotExist:
                            error_count += 1
                            error_msg = f'Fehler in Zeile {i + 1}: Lager "{warehouse_name}" nicht gefunden.'
                            error_msgs.append(error_msg)
                            continue

                    # Variante finden, falls angegeben
                    variant = None
                    if variant_name_idx is not None and variant_name_idx < len(fields) and fields[
                        variant_name_idx].strip():
                        variant_name = fields[variant_name_idx].strip()
                        try:
                            variant = ProductVariant.objects.get(parent_product=product, name=variant_name)
                        except ProductVariant.DoesNotExist:
                            error_count += 1
                            error_msg = f'Fehler in Zeile {i + 1}: Variante "{variant_name}" für Produkt nicht gefunden.'
                            error_msgs.append(error_msg)
                            continue

                    # Datum parsen, falls angegeben
                    purchase_date = None
                    if purchase_date_idx is not None and purchase_date_idx < len(fields) and fields[
                        purchase_date_idx].strip():
                        try:
                            purchase_date_str = fields[purchase_date_idx].strip()
                            purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            error_count += 1
                            error_msg = f'Fehler in Zeile {i + 1}: Ungültiges Kaufdatum "{fields[purchase_date_idx]}".'
                            error_msgs.append(error_msg)
                            continue

                    expiry_date = None
                    if expiry_date_idx is not None and expiry_date_idx < len(fields) and fields[
                        expiry_date_idx].strip():
                        try:
                            expiry_date_str = fields[expiry_date_idx].strip()
                            expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            error_count += 1
                            error_msg = f'Fehler in Zeile {i + 1}: Ungültiges Ablaufdatum "{fields[expiry_date_idx]}".'
                            error_msgs.append(error_msg)
                            continue

                    # Notizen extrahieren
                    notes = fields[notes_idx].strip() if notes_idx is not None and notes_idx < len(fields) else ''

                    # Seriennummer erstellen oder aktualisieren
                    if existing_serial and update_existing:
                        # Aktualisieren
                        existing_serial.product = product
                        existing_serial.status = status
                        existing_serial.warehouse = warehouse
                        existing_serial.variant = variant
                        existing_serial.purchase_date = purchase_date
                        existing_serial.expiry_date = expiry_date
                        existing_serial.notes = notes
                        existing_serial.save()
                        updated_count += 1
                    else:
                        # Neu erstellen
                        SerialNumber.objects.create(
                            product=product,
                            serial_number=serial_number,
                            status=status,
                            warehouse=warehouse,
                            variant=variant,
                            purchase_date=purchase_date,
                            expiry_date=expiry_date,
                            notes=notes
                        )
                        created_count += 1

                    # Produkt für Seriennummern aktivieren, falls noch nicht geschehen
                    if not product.has_serial_numbers:
                        product.has_serial_numbers = True
                        product.save()

                except Exception as e:
                    error_count += 1
                    error_msg = f'Fehler in Zeile {i + 1}: {str(e)}'
                    error_msgs.append(error_msg)

            # Import-Log aktualisieren
            import_log.status = 'completed' if error_count == 0 else 'completed_with_errors'
            import_log.rows_processed = created_count + updated_count + error_count
            import_log.rows_created = created_count
            import_log.rows_updated = updated_count
            import_log.rows_error = error_count
            import_log.notes = f"Import abgeschlossen: {created_count} erstellt, {updated_count} aktualisiert, {error_count} Fehler"

            if error_msgs:
                import_log.error_details = '\n'.join(error_msgs)

            import_log.save()

            if error_count > 0:
                messages.warning(request,
                                 f'Import mit Fehlern abgeschlossen. {created_count} erstellt, {updated_count} aktualisiert, {error_count} Fehler.')
            else:
                messages.success(request,
                                 f'Import erfolgreich abgeschlossen. {created_count} erstellt, {updated_count} aktualisiert.')

            return redirect('import_log_detail', pk=import_log.pk)

        except Exception as e:
            import_log.status = 'failed'
            import_log.notes = f'Fehler beim Import: {str(e)}'
            import_log.save()
            messages.error(request, import_log.notes)
            return redirect('import_serialnumbers')

    # Für GET-Anfragen oder bei Fehlern im POST
    context = {
        'title': 'Seriennummern importieren',
        'description': 'Importieren Sie Seriennummern aus einer CSV-Datei.',
        'expected_format': 'product_sku,serial_number,status,warehouse_name,purchase_date,expiry_date,variant_name,notes',
        'example': 'P1001,SN12345,in_stock,Hauptlager,2023-01-01,2025-01-01,Standard,Neue Lieferung',
        'required_columns': ['product_sku', 'serial_number'],
        'optional_columns': ['status', 'warehouse_name', 'purchase_date', 'expiry_date', 'variant_name', 'notes'],
        'warehouses': Warehouse.objects.filter(is_active=True),
        'status_choices': SerialNumber.status_choices,
    }

    return render(request, 'core/serialnumber/serialnumber_import.html', context)