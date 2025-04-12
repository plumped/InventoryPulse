import mimetypes

from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.db.models.aggregates import Sum
from django.db.models.query_utils import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect

from suppliers.models import SupplierProduct
from .models import Product, ProductVariant


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
def products_search(request):
    """API-Endpunkt für die Suche nach Produkten mit Bestandsinformationen und bevorzugtem Lieferanten."""
    search_query = request.GET.get('q', '')

    if not search_query or len(search_query) < 2:
        return JsonResponse([], safe=False)

    # Produkte suchen
    products = Product.objects.filter(
        Q(name__icontains=search_query) |
        Q(sku__icontains=search_query) |
        Q(barcode__icontains=search_query)
    ).prefetch_related('supplier_products', 'productwarehouse_set')

    # Maximal 50 Ergebnisse zurückgeben
    products = products[:50]

    results = []
    for product in products:
        # Aktuellen Bestand berechnen
        stock = product.productwarehouse_set.aggregate(total=Sum('quantity'))['total'] or 0

        # Bevorzugten Lieferanten ermitteln
        preferred_supplier = None
        try:
            supplier_product = SupplierProduct.objects.filter(
                product=product,
                is_preferred=True
            ).select_related('supplier').first()

            if supplier_product:
                preferred_supplier = {
                    'id': supplier_product.supplier.id,
                    'name': supplier_product.supplier.name
                }
            else:
                # Fallback: Den ersten verfügbaren Lieferanten verwenden
                supplier_product = SupplierProduct.objects.filter(
                    product=product
                ).select_related('supplier').first()

                if supplier_product:
                    preferred_supplier = {
                        'id': supplier_product.supplier.id,
                        'name': supplier_product.supplier.name
                    }
        except:
            pass

        # Produktdaten zusammenstellen
        product_data = {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'stock': float(stock),
            'minimum_stock': float(product.minimum_stock),
            'unit': product.unit,
            'preferred_supplier': preferred_supplier
        }

        results.append(product_data)

    return JsonResponse(results, safe=False)

@login_required
def api_product_variants(request):
    """API-Endpunkt, um Varianten für ein bestimmtes Produkt zu erhalten."""
    product_id = request.GET.get('product_id', None)

    if not product_id:
        return JsonResponse([], safe=False)

    variants = ProductVariant.objects.filter(
        parent_product_id=product_id,
        is_active=True
    ).values('id', 'name', 'value')

    return JsonResponse(list(variants), safe=False)


def documentation_view(request, path=''):
    """Weiterleitung zur Dokumentation."""
    if not path:
        return redirect('/static/docs/index.html')
    return redirect(f'/static/docs/{path}')

    # MIME-Typ bestimmen
    content_type, encoding = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'text/html'  # Standard-MIME-Typ

    # Datei lesen und ausliefern
    with open(file_path, 'rb') as f:
        file_content = f.read()

    return HttpResponse(file_content, content_type=content_type)