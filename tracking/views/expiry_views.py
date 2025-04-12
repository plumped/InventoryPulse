from datetime import timedelta

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render
from django.utils import timezone

from core.models import SerialNumber, BatchNumber, Category
from core.utils.filters import filter_expiring_serials, filter_expiring_batches
from core.utils.pagination import paginate_queryset


@login_required
@permission_required('products.view_product', raise_exception=True)
def expiry_management(request):
    """Zentrale Verwaltung aller Produkte mit Verfallsdaten."""

    today = timezone.now().date()
    days_threshold = request.GET.get('days_threshold', '30')
    try:
        days_threshold = int(days_threshold)
    except ValueError:
        days_threshold = 30

    filters = {
        'expiry': request.GET.get('filter', 'all'),
        'search': request.GET.get('search', ''),
        'category': request.GET.get('category', ''),
        'days': days_threshold,
    }

    serials = SerialNumber.objects.filter(expiry_date__isnull=False)
    batches = BatchNumber.objects.filter(expiry_date__isnull=False)

    serials = filter_expiring_serials(serials, filters, today)
    batches = filter_expiring_batches(batches, filters, today)

    # Statistiken
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

    serials = paginate_queryset(serials, request.GET.get('serials_page'), per_page=25)
    batches = paginate_queryset(batches, request.GET.get('batches_page'), per_page=25)

    context = {
        'serials': serials,
        'batches': batches,
        'serial_stats': serial_stats,
        'batch_stats': batch_stats,
        'categories': Category.objects.all(),
        'expiry_filter': filters['expiry'],
        'days_threshold': filters['days'],
        'search_query': filters['search'],
        'category_filter': filters['category'],
        'today': today,
    }

    return render(request, 'core/product/expiry_management.html', context)
