from datetime import timedelta

from django.db.models import Q


def filter_product_serials(queryset, filters):
    if filters.get('status'):
        queryset = queryset.filter(status=filters['status'])
    if filters.get('warehouse'):
        queryset = queryset.filter(warehouse_id=filters['warehouse'])
    if filters.get('variant'):
        queryset = queryset.filter(variant_id=filters['variant'])
    if filters.get('product'):
        queryset = queryset.filter(product_id=filters['product'])
    if filters.get('search'):
        queryset = queryset.filter(
            Q(serial_number__icontains=filters['search']) |
            Q(product__name__icontains=filters['search']) |
            Q(variant__name__icontains=filters['search'])
        )
    return queryset


def filter_product_serials_by_product(queryset, filters, product):
    queryset = queryset.filter(product=product)

    if filters.get('status'):
        queryset = queryset.filter(status=filters['status'])
    if filters.get('warehouse'):
        queryset = queryset.filter(warehouse_id=filters['warehouse'])
    if filters.get('variant'):
        queryset = queryset.filter(variant_id=filters['variant'])
    if filters.get('search'):
        queryset = queryset.filter(serial_number__icontains=filters['search'])

    return queryset

def filter_product_batches(queryset, filters, product, today):
    queryset = queryset.filter(product=product)

    if filters.get('warehouse'):
        queryset = queryset.filter(warehouse_id=filters['warehouse'])
    if filters.get('variant'):
        queryset = queryset.filter(variant_id=filters['variant'])
    if filters.get('search'):
        queryset = queryset.filter(batch_number__icontains=filters['search'])

    expiry_filter = filters.get('expiry')
    if expiry_filter == 'expired':
        queryset = queryset.filter(expiry_date__lt=today)
    elif expiry_filter == 'expiring_soon':
        queryset = queryset.filter(expiry_date__gte=today, expiry_date__lte=today + filters.get('days', 30))
    elif expiry_filter == 'valid':
        queryset = queryset.filter(expiry_date__gt=today + filters.get('days', 30))

    return queryset

def filter_expiring_serials(queryset, filters, today):
    expiry_filter = filters.get('expiry')
    if expiry_filter == 'expired':
        queryset = queryset.filter(expiry_date__lt=today)
    elif expiry_filter == 'expiring_soon':
        queryset = queryset.filter(expiry_date__gte=today, expiry_date__lte=today + filters.get('days', 30))
    elif expiry_filter == 'valid':
        queryset = queryset.filter(expiry_date__gt=today + filters.get('days', 30))

    if filters.get('search'):
        queryset = queryset.filter(
            Q(product__name__icontains=filters['search']) |
            Q(serial_number__icontains=filters['search'])
        )

    if filters.get('category'):
        queryset = queryset.filter(product__category_id=filters['category'])

    return queryset

def filter_expiring_batches(queryset, filters, today):
    expiry_filter = filters.get('expiry')
    days = filters.get('days', 30)

    if expiry_filter == 'expired':
        queryset = queryset.filter(expiry_date__lt=today)
    elif expiry_filter == 'expiring_soon':
        queryset = queryset.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=days))
    elif expiry_filter == 'valid':
        queryset = queryset.filter(expiry_date__gt=today + timedelta(days=days))

    if filters.get('search'):
        queryset = queryset.filter(
            Q(product__name__icontains=filters['search']) |
            Q(batch_number__icontains=filters['search'])
        )

    if filters.get('category'):
        queryset = queryset.filter(product__category_id=filters['category'])

    return queryset