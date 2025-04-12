from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.templatetags.static import static

from accessmanagement.models import WarehouseAccess
from core.forms import ProductImportForm, SupplierImportForm, CategoryImportForm, SupplierProductImportForm, \
    WarehouseImportForm, DepartmentImportForm, WarehouseProductImportForm
from core.importers.categories import CategoryImporter
from core.importers.products import ProductImporter, SupplierProductImporter
from core.importers.suppliers import SupplierImporter
from core.models import SerialNumber, ImportLog, Product, ProductWarehouse, ProductVariant
from core.utils.imports import handle_csv_import
from core.utils.stock import get_accessible_stock
from inventory.models import Warehouse, StockMovement
from organization.models import Department


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
    return handle_csv_import(
        form_class=ProductImportForm,
        importer_class=ProductImporter,
        request=request,
        template_name='core/import/import_form.html',
        success_redirect='import_log_detail',
        extra_context={
            'title': 'Produkte importieren',
            'template_file_url': static('files/product_import_template.csv'),
        }
    )


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
                            total_stock = get_accessible_stock(product, accessible_warehouses)
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
