from datetime import timedelta

from django.db.models import Q

def apply_text_filter(queryset, field_name, value):
    if value:
        return queryset.filter(**{f"{field_name}__icontains": value})
    return queryset

def apply_exact_filter(queryset, field_name, value):
    if value:
        return queryset.filter(**{field_name: value})
    return queryset

def apply_related_filter(queryset, field_path, value):
    if value:
        return queryset.filter(**{f"{field_path}__id": value})
    return queryset

def apply_bool_flag_filter(queryset, field_name, flag):
    if flag == 'yes':
        return queryset.filter(**{field_name: True})
    elif flag == 'no':
        return queryset.filter(**{field_name: False})
    return queryset

def apply_filter_map(queryset, filters, field_map):
    for key, config in field_map.items():
        value = filters.get(key)
        if not value:
            continue

        if isinstance(config, tuple):
            field, filter_type = config
        else:
            field = config
            filter_type = 'exact'

        if filter_type == 'text':
            queryset = apply_text_filter(queryset, field, value)
        elif filter_type == 'related':
            queryset = apply_related_filter(queryset, field, value)
        elif filter_type == 'bool':
            queryset = apply_bool_flag_filter(queryset, field, value)
        else:
            queryset = apply_exact_filter(queryset, field, value)

    return queryset

def apply_expiry_filter(queryset, expiry_filter, today, days=30):
    if expiry_filter == 'expired':
        return queryset.filter(expiry_date__lt=today)
    elif expiry_filter == 'expiring_soon':
        return queryset.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=days))
    elif expiry_filter == 'valid':
        return queryset.filter(expiry_date__gt=today + timedelta(days=days))
    return queryset




def filter_product_serials(queryset, filters):
    field_map = {
        'status': 'status',
        'warehouse': 'warehouse_id',
        'variant': 'variant_id',
        'product': 'product_id',
    }

    queryset = apply_filter_map(queryset, filters, field_map)

    if search := filters.get('search'):
        queryset = queryset.filter(
            Q(serial_number__icontains=search) |
            Q(product__name__icontains=search) |
            Q(variant__name__icontains=search)
        )

    return queryset

def filter_product_serials_by_product(queryset, filters, product):
    queryset = queryset.filter(product=product)

    field_map = {
        'status': 'status',
        'warehouse': 'warehouse_id',
        'variant': 'variant_id',
    }

    for key, field in field_map.items():
        queryset = apply_exact_filter(queryset, field, filters.get(key))

    queryset = apply_text_filter(queryset, 'serial_number', filters.get('search'))

    return queryset


def filter_product_batches(queryset, filters, product, today):
    queryset = queryset.filter(product=product)

    field_map = {
        'warehouse': 'warehouse_id',
        'variant': 'variant_id',
    }
    queryset = apply_filter_map(queryset, filters, field_map)
    queryset = apply_text_filter(queryset, 'batch_number', filters.get('search'))
    queryset = apply_expiry_filter(queryset, filters.get('expiry'), today, filters.get('days', 30))

    return queryset


def filter_expiring_serials(queryset, filters, today):
    queryset = apply_expiry_filter(queryset, filters.get('expiry'), today, filters.get('days', 30))

    if search := filters.get('search'):
        queryset = queryset.filter(
            Q(product__name__icontains=search) |
            Q(serial_number__icontains=search)
        )

    queryset = apply_exact_filter(queryset, 'product__category_id', filters.get('category'))
    return queryset


def filter_expiring_batches(queryset, filters, today):
    queryset = apply_expiry_filter(queryset, filters.get('expiry'), today, filters.get('days', 30))

    if search := filters.get('search'):
        queryset = queryset.filter(
            Q(product__name__icontains=search) |
            Q(batch_number__icontains=search)
        )

    queryset = apply_exact_filter(queryset, 'product__category_id', filters.get('category'))
    return queryset


def filter_users(queryset, filters):
    if search := filters.get('search'):
        queryset = queryset.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    field_map = {
        'status': ('is_active', 'bool'),
        'group': ('groups', 'related'),
    }

    return apply_filter_map(queryset, filters, field_map)


def filter_departments(queryset, filters):
    """Filtert Abteilungen nach Suchbegriff (z. B. Name oder Code)."""
    if filters.get('search'):
        queryset = queryset.filter(
            Q(name__icontains=filters['search']) |
            Q(code__icontains=filters['search'])
        )
    return queryset

def filter_taxes(queryset, filters):
    """Filtert Steuersätze nach Name oder Rate."""
    if filters.get('search'):
        queryset = queryset.filter(
            Q(name__icontains=filters['search']) |
            Q(rate__icontains=filters['search'])
        )
    return queryset

def filter_interface_types(queryset, filters):
    """Filter für Schnittstellentypen nach Name."""
    if filters.get('search'):
        queryset = queryset.filter(name__icontains=filters['search'])
    return queryset

def filter_supplier_interfaces(queryset, filters):
    """Filter für SupplierInterface nach Name, Typ und Aktiv-Status."""
    if filters.get('search'):
        queryset = queryset.filter(name__icontains=filters['search'])

    if filters.get('type'):
        queryset = queryset.filter(interface_type_id=filters['type'])

    if filters.get('status') == 'active':
        queryset = queryset.filter(is_active=True)
    elif filters.get('status') == 'inactive':
        queryset = queryset.filter(is_active=False)

    return queryset

def filter_company_addresses(queryset, filters):
    field_map = {
        'search': ('name', 'text'),
        'search_city': ('city', 'text'),
        'search_street': ('street', 'text'),
        'search_postcode': ('postcode', 'text'),
        'type': 'address_type',
        'is_default': ('is_default', 'bool'),
    }

    # Für die 4-fach Suche auf denselben Begriff: simulate keys
    if filters.get('search'):
        filters = {
            **filters,
            'search_city': filters['search'],
            'search_street': filters['search'],
            'search_postcode': filters['search'],
        }

    return apply_filter_map(queryset, filters, field_map)



