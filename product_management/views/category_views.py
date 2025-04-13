from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404, redirect

from product_management.forms.categories_forms import CategoryForm
from product_management.models.categories_models import Category
from product_management.models.products_models import Product


@login_required
@permission_required('categories.view_categories', raise_exception=True)
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
