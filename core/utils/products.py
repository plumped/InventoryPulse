
from core.utils.access import get_accessible_warehouses
from core.utils.stock import get_accessible_stock
from product_management.models.products_models import Product


def get_filtered_products(request, filter_low_stock=False):
    warehouses = get_accessible_warehouses(request.user)
    products = Product.objects.select_related('category').all()
    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    stock_status = request.GET.get('stock_status', '')

    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search) | Q(barcode__icontains=search))
    if category:
        products = products.filter(category_id=category)

    filtered = []
    for product in products:
        stock = get_accessible_stock(product, warehouses)
        product.accessible_stock = stock

        if filter_low_stock and stock < product.minimum_stock:
            filtered.append(product)
        elif not filter_low_stock:
            if stock_status == 'low' and (stock <= product.minimum_stock and stock > 0):
                filtered.append(product)
            elif stock_status == 'ok' and stock > product.minimum_stock:
                filtered.append(product)
            elif stock_status == 'out' and stock == 0:
                filtered.append(product)
            elif not stock_status:
                filtered.append(product)

    return sorted(filtered, key=lambda p: p.name)
