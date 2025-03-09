import csv
import io
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
    ProductImportForm, WarehouseImportForm, DepartmentImportForm, WarehouseProductImportForm
from .importers import SupplierProductImporter, CategoryImporter, SupplierImporter, ProductImporter
from .models import Product, Category, ImportLog, ProductWarehouse
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