import csv
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import models
from django.http import HttpResponse

from inventory.models import Warehouse


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Kategorie"
        verbose_name_plural = "Kategorien"
        ordering = ['name']

class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    current_stock = models.IntegerField(default=0)
    minimum_stock = models.IntegerField(default=0)
    unit = models.CharField(max_length=20, default="Stück")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    warehouses = models.ManyToManyField(Warehouse, through='ProductWarehouse')

    def __str__(self):
        return self.name


class ProductWarehouse(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('product', 'warehouse')


# Updated ImportLog model in core/models.py

# Updated ImportLog model in core/models.py

class ImportLog(models.Model):
    STATUS_CHOICES = (
        ('completed', 'Completed'),
        ('completed_with_errors', 'Completed with Errors'),
        ('processing', 'Processing'),
        ('failed', 'Failed'),
    )

    IMPORT_TYPE_CHOICES = (
        ('products', 'Products'),
        ('categories', 'Categories'),
        ('suppliers', 'Suppliers'),
        ('supplier_products', 'Supplier Products'),
        ('warehouses', 'Warehouses'),
        ('departments', 'Departments'),
        ('warehouse_products', 'Warehouse Products'),
    )

    file_name = models.CharField(max_length=255)
    import_type = models.CharField(max_length=50, choices=IMPORT_TYPE_CHOICES, default='products')
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='processing')

    # Keep original fields for compatibility
    total_records = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)

    # New more descriptive fields
    rows_processed = models.IntegerField(default=0)
    rows_created = models.IntegerField(default=0)
    rows_updated = models.IntegerField(default=0)
    rows_error = models.IntegerField(default=0)

    error_file = models.FileField(upload_to='import_errors/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='import_logs')

    # Additional fields for error handling
    notes = models.TextField(blank=True, null=True)
    error_details = models.TextField(blank=True, null=True)

    # Properties for backwards compatibility
    @property
    def successful_rows(self):
        return self.success_count

    @successful_rows.setter
    def successful_rows(self, value):
        self.success_count = value
        self.rows_created = value  # Update the new field too

    @property
    def failed_rows(self):
        return self.error_count

    @failed_rows.setter
    def failed_rows(self, value):
        self.error_count = value
        self.rows_error = value  # Update the new field too

    @property
    def total_rows(self):
        return self.total_records

    @total_rows.setter
    def total_rows(self, value):
        self.total_records = value
        self.rows_processed = value  # Update the new field too

    @property
    def user(self):
        return self.created_by

    @user.setter
    def user(self, value):
        self.created_by = value

    @property
    def started_by(self):
        return self.created_by

    @started_by.setter
    def started_by(self, value):
        self.created_by = value

    @property
    def has_errors(self):
        return self.error_count > 0

    @property
    def filename(self):
        return self.file_name

    def success_rate(self):
        if self.total_records > 0:
            return round((self.success_count / self.total_records) * 100, 1)
        return 0

    class Meta:
        ordering = ['-created_at']


@login_required
def import_log_list(request):
    # Get all users for the filter dropdown
    users = User.objects.all()

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

    if 'daterange' in request.GET and request.GET['daterange']:
        date_range = request.GET['daterange'].split(' - ')
        if len(date_range) == 2:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%d')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59)
            queryset = queryset.filter(created_at__range=[start_date, end_date])

    # Apply sorting
    sort_param = request.GET.get('sort', '-created_at')
    if sort_param:
        queryset = queryset.order_by(sort_param)

    # Pagination
    paginator = Paginator(queryset, 25)  # Show 25 logs per page
    page_number = request.GET.get('page')
    import_logs = paginator.get_page(page_number)

    context = {
        'import_logs': import_logs,
        'users': users,
    }

    return render(request, 'import_log_list.html', context)


@login_required
def import_log_detail(request, log_id):
    log = get_object_or_404(ImportLog, id=log_id)
    return render(request, 'import_log_detail.html', {'log': log})


@login_required
def download_error_file(request, log_id):
    log = get_object_or_404(ImportLog, id=log_id)
    if log.error_file:
        response = HttpResponse(log.error_file.read(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{log.file_name}_errors.csv"'
        return response
    return HttpResponse("Error file not found", status=404)


@login_required
def delete_import_log(request, log_id):
    if request.method == 'POST':
        log = get_object_or_404(ImportLog, id=log_id)
        log.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


@login_required
def bulk_delete_import_logs(request):
    if request.method == 'POST':
        ids = request.POST.get('ids', '').split(',')
        ImportLog.objects.filter(id__in=ids).delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


@login_required
def export_import_logs(request):
    format_type = request.GET.get('format', 'csv')

    # Filter logs based on request parameters
    queryset = ImportLog.objects.all()

    # Check if specific IDs were requested
    if 'ids' in request.GET and request.GET['ids']:
        ids = request.GET['ids'].split(',')
        queryset = queryset.filter(id__in=ids)
    else:
        # Apply the same filters as the list view
        if 'search' in request.GET and request.GET['search']:
            queryset = queryset.filter(file_name__icontains=request.GET['search'])

        if 'status' in request.GET and request.GET['status']:
            queryset = queryset.filter(status=request.GET['status'])

        if 'user' in request.GET and request.GET['user']:
            queryset = queryset.filter(created_by_id=request.GET['user'])

        if 'daterange' in request.GET and request.GET['daterange']:
            date_range = request.GET['daterange'].split(' - ')
            if len(date_range) == 2:
                start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%d')
                end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(created_at__range=[start_date, end_date])

    # CSV export
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="import_logs.csv"'

        writer = csv.writer(response)
        writer.writerow(['ID', 'Date', 'Filename', 'Status', 'Items Processed',
                         'Success Count', 'Error Count', 'User'])

        for log in queryset:
            writer.writerow([
                log.id,
                log.created_at.strftime('%Y-%m-%d %H:%M'),
                log.file_name,
                log.status,
                log.total_records,
                log.success_count,
                log.error_count,
                log.created_by.username
            ])

        return response

    # Excel export
    elif format_type == 'xlsx':
        import openpyxl
        from openpyxl.styles import Font

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Import Logs"

        # Add header row with bold font
        headers = ['ID', 'Date', 'Filename', 'Status', 'Items Processed',
                   'Success Count', 'Error Count', 'User']

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True)

        # Add data rows
        for row_num, log in enumerate(queryset, 2):
            ws.cell(row=row_num, column=1, value=log.id)
            ws.cell(row=row_num, column=2, value=log.created_at.strftime('%Y-%m-%d %H:%M'))
            ws.cell(row=row_num, column=3, value=log.file_name)
            ws.cell(row=row_num, column=4, value=log.status)
            ws.cell(row=row_num, column=5, value=log.total_records)
            ws.cell(row=row_num, column=6, value=log.success_count)
            ws.cell(row=row_num, column=7, value=log.error_count)
            ws.cell(row=row_num, column=8, value=log.created_by.username)

        # Create response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="import_logs.xlsx"'

        # Save workbook to response
        wb.save(response)
        return response

    return HttpResponse("Unsupported format", status=400)


class ImportError(models.Model):
    import_log = models.ForeignKey(ImportLog, related_name='errors', on_delete=models.CASCADE)
    row_number = models.IntegerField()
    error_message = models.TextField()
    row_data = models.TextField(blank=True)
    field_name = models.CharField(max_length=100, blank=True)
    field_value = models.TextField(blank=True)

    class Meta:
        ordering = ['row_number']


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    departments = models.ManyToManyField('inventory.Department', related_name='user_profiles', blank=True)

    def __str__(self):
        return f"Profil von {self.user.username}"