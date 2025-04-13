from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import models
from django.db.models.aggregates import Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from accessmanagement.models import WarehouseAccess
from core.utils.pagination import paginate_queryset
from core.utils.products import get_filtered_products
from inventory.models import Warehouse, StockMovement
from product_management.forms.product_forms import ProductForm
from product_management.models.categories import Category
from product_management.models.products import ProductWarehouse, Product
from suppliers.models import SupplierProduct
from tracking.models import SerialNumber


@login_required
@permission_required('products.view_product', raise_exception=True)
def product_list(request):
    filtered_products = get_filtered_products(request)
    products = paginate_queryset(filtered_products, request.GET.get('page'), per_page=25)

    categories = Category.objects.all().order_by('name')
    context = {
        'products': products,
        'categories': categories,
        'search_query': request.GET.get('search', ''),
        'category_id': request.GET.get('category', ''),
        'stock_status': request.GET.get('stock_status', ''),
    }
    return render(request, 'core/product_list.html', context)


@login_required
@permission_required('product', 'create')
def product_create(request):
    """Create a new product."""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()

            # Bestandsbewegung für Anfangsbestand erstellen, wenn > 0
            initial_stock = form.cleaned_data.get('initial_stock', 0)
            if initial_stock > 0:
                # Standardlager abrufen oder erstellen
                try:
                    warehouse = Warehouse.objects.filter(is_active=True).first()
                    if not warehouse:
                        warehouse = Warehouse.objects.create(
                            name='Hauptlager',
                            code='MAIN'
                        )

                    # Produktlager-Eintrag erstellen
                    ProductWarehouse.objects.create(
                        product=product,
                        warehouse=warehouse,
                        quantity=initial_stock
                    )

                    # Bestandsbewegung erstellen
                    StockMovement.objects.create(
                        product=product,
                        warehouse=warehouse,
                        quantity=initial_stock,
                        movement_type='in',
                        reference='Anfangsbestand',
                        created_by=request.user
                    )
                except Exception as e:
                    messages.error(request, f'Fehler bei der Erstellung des Anfangsbestands: {str(e)}')

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

    # Lager abrufen, auf die der Benutzer Zugriff hat
    if request.user.is_superuser:
        accessible_warehouses = Warehouse.objects.filter(is_active=True)
    else:
        user_departments = request.user.profile.departments.all()
        warehouse_access = WarehouseAccess.objects.filter(
            department__in=user_departments
        ).values_list('warehouse', flat=True)
        accessible_warehouses = Warehouse.objects.filter(id__in=warehouse_access, is_active=True)

    # Aktuellen Bestand berechnen
    total_accessible_stock = ProductWarehouse.objects.filter(
        product=product,
        warehouse__in=accessible_warehouses
    ).aggregate(total=Sum('quantity'))['total'] or 0

    # Prüfen, ob Funktionen deaktivierbar sind
    has_variants = False
    has_serial_numbers = False
    has_batches = False
    has_expiry_dates = False

    if hasattr(product, 'variants'):
        has_variants = product.variants.exists()

    if hasattr(product, 'serial_numbers'):
        has_serial_numbers = product.serial_numbers.exists()
        # Prüfen, ob Seriennummern mit Verfallsdaten existieren
        has_expiry_dates = has_expiry_dates or product.serial_numbers.filter(expiry_date__isnull=False).exists()

    if hasattr(product, 'batches'):
        has_batches = product.batches.exists()
        # Prüfen, ob Chargen mit Verfallsdaten existieren
        has_expiry_dates = has_expiry_dates or product.batches.filter(expiry_date__isnull=False).exists()

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            # Das Produkt ohne Bestandsänderung speichern
            product = form.save()

            messages.success(request, f'Produkt "{product.name}" wurde erfolgreich aktualisiert.')
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductForm(instance=product)

    context = {
        'form': form,
        'total_accessible_stock': total_accessible_stock,
        'has_variants': has_variants,
        'has_serial_numbers': has_serial_numbers,
        'has_batches': has_batches,
        'has_expiry_dates': has_expiry_dates
    }

    return render(request, 'core/product_form.html', context)


@login_required
@permission_required('products.view_product', raise_exception=True)
def product_detail(request, pk):
    """Show details for a specific product."""
    product = get_object_or_404(Product, pk=pk)

    # Lieferanteninformationen
    supplier_products = SupplierProduct.objects.filter(product=product).select_related('supplier')

    # Bestandsbewegungen
    movements = StockMovement.objects.filter(product=product).select_related('created_by', 'warehouse').order_by(
        '-created_at')[:20]

    # Primärbild abrufen, falls vorhanden
    primary_photo = product.photos.filter(is_primary=True).first()

    # Anzahl der Varianten, Seriennummern und Chargen
    variant_count = product.variants.count()
    serial_count = product.serial_numbers.count()
    batch_count = product.batches.count()

    # Lager, auf die der Benutzer Zugriff hat
    if request.user.is_superuser:
        accessible_warehouses = Warehouse.objects.filter(is_active=True)
    else:
        accessible_warehouses = [w for w in Warehouse.objects.filter(is_active=True)
                                 if WarehouseAccess.has_access(request.user, w, 'view')]

    # Varianten mit kritischem Bestand
    # Hier holen wir zuerst alle Varianten
    all_variants = product.variants.all()

    # Spezieller Schwellwert für "kritischen Bestand"
    low_stock_threshold = 3

    # Varianten mit kritischem Bestand
    low_stock_variants = []

    # Für jede Variante prüfen, ob der Gesamtbestand niedrig ist
    for variant in all_variants:
        # Versuchen, das total_stock über VariantWarehouse zu berechnen
        try:
            from django.db.models import Sum
            from inventory.models import VariantWarehouse

            total_stock = VariantWarehouse.objects.filter(
                variant=variant,
                warehouse__in=accessible_warehouses
            ).aggregate(total=Sum('quantity'))['total'] or 0

            # Wenn es niedrig ist, zur Liste hinzufügen
            if total_stock < low_stock_threshold and total_stock > 0:
                # Wir fügen das berechnete total_stock als Attribut hinzu
                variant.total_stock = total_stock
                low_stock_variants.append(variant)

                # Nur max. 5 Varianten in die Liste
                if len(low_stock_variants) >= 5:
                    break
        except (ImportError, AttributeError):
            # Wenn es keine VariantWarehouse-Tabelle gibt, leere Liste verwenden
            pass

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

    # NEU: Lagerbestandsinformationen
    # Bestand in allen zugänglichen Lagern für dieses Produkt
    warehouse_stocks = ProductWarehouse.objects.filter(
        product=product,
        warehouse__in=accessible_warehouses
    ).select_related('warehouse').order_by('warehouse__name')

    # Gesamtbestand über alle zugänglichen Lager
    total_accessible_stock = warehouse_stocks.aggregate(total=models.Sum('quantity'))['total'] or 0

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
        'serial_status_counts': serial_status_counts,
        'warehouse_stocks': warehouse_stocks,
        'total_accessible_stock': total_accessible_stock,
        'accessible_warehouses': accessible_warehouses,
    }

    return render(request, 'core/product_detail.html', context)


@login_required
@permission_required('products.view_product', raise_exception=True)
def low_stock_list(request):
    products = get_filtered_products(request, filter_low_stock=True)
    return render(request, 'core/low_stock_list.html', {'products': products, 'title': 'Kritische Bestände'})
