from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import ProductVariantForm, ProductVariantTypeForm
from core.models import SerialNumber, BatchNumber
from core.utils.view_helpers import handle_model_update
from inventory.models import Warehouse
from product_management.models.products import ProductVariantType, ProductVariant, Product


@login_required
@permission_required('products.view_product', raise_exception=True)
def variant_type_list(request):
    """Zeigt alle Variantentypen an."""
    variant_types = ProductVariantType.objects.all()

    # Varianten pro Typ zählen
    variant_types_with_count = []
    for vt in variant_types:
        variant_count = ProductVariant.objects.filter(variant_type=vt).count()
        variant_types_with_count.append({
            'type': vt,
            'variant_count': variant_count
        })

    context = {
        'variant_types': variant_types_with_count,
    }

    return render(request, 'core/variant_type/variant_type_list.html', context)


@login_required
@permission_required('product', 'create')
def variant_type_add(request):
    """Erstellt einen neuen Variantentyp."""
    if request.method == 'POST':
        form = ProductVariantTypeForm(request.POST)
        if form.is_valid():
            variant_type = form.save()
            messages.success(request, f'Variantentyp "{variant_type.name}" wurde erfolgreich erstellt.')
            return redirect('variant_type_list')
    else:
        form = ProductVariantTypeForm()

    context = {
        'form': form,
    }

    return render(request, 'core/variant_type/variant_type_form.html', context)


@login_required
@permission_required('product', 'edit')
def variant_type_update(request, pk):
    """Aktualisiert einen Variantentyp."""
    variant_type = get_object_or_404(ProductVariantType, pk=pk)

    if request.method == 'POST':
        form = ProductVariantTypeForm(request.POST, instance=variant_type)
        if form.is_valid():
            variant_type = form.save()
            messages.success(request, f'Variantentyp "{variant_type.name}" wurde erfolgreich aktualisiert.')
            return redirect('variant_type_list')
    else:
        form = ProductVariantTypeForm(instance=variant_type)

    context = {
        'form': form,
        'variant_type': variant_type,
    }

    return render(request, 'core/variant_type/variant_type_form.html', context)


@login_required
@permission_required('product', 'delete')
def variant_type_delete(request, pk):
    """Löscht einen Variantentyp."""
    variant_type = get_object_or_404(ProductVariantType, pk=pk)

    # Prüfen, ob Varianten diesen Typ verwenden
    variant_count = ProductVariant.objects.filter(variant_type=variant_type).count()

    if request.method == 'POST':
        if variant_count > 0 and 'confirm_delete' not in request.POST:
            messages.error(request, f'Dieser Variantentyp wird von {variant_count} Varianten verwendet. '
                                    f'Löschen bestätigen, um trotzdem fortzufahren.')
            return redirect('variant_type_delete', pk=variant_type.pk)

        variant_type.delete()
        messages.success(request, f'Variantentyp "{variant_type.name}" wurde erfolgreich gelöscht.')
        return redirect('variant_type_list')

    context = {
        'variant_type': variant_type,
        'variant_count': variant_count,
    }

    return render(request, 'core/variant_type/variant_type_confirm_delete.html', context)


# ------------------------------------------------------------------------------
# Produktvarianten
# ------------------------------------------------------------------------------

@login_required
@permission_required('products.view_product', raise_exception=True)
def product_variants(request, pk):
    """Zeigt alle Varianten eines Produkts an."""
    product = get_object_or_404(Product, pk=pk)
    variants = product.variants.all()

    context = {
        'product': product,
        'variants': variants,
    }

    return render(request, 'core/product/product_variants.html', context)


@login_required
@permission_required('products.view_product', raise_exception=True)
def product_variant_detail(request, pk, variant_id):
    """Zeigt Details zu einer Produktvariante an."""
    product = get_object_or_404(Product, pk=pk)
    variant = get_object_or_404(ProductVariant, pk=variant_id, parent_product=product)

    # Seriennummern für diese Variante
    serial_numbers = SerialNumber.objects.filter(variant=variant)

    # Chargen für diese Variante
    batches = BatchNumber.objects.filter(variant=variant)

    context = {
        'product': product,
        'variant': variant,
        'serial_numbers': serial_numbers,
        'batches': batches,
    }

    return render(request, 'core/product/product_variant_detail.html', context)


@login_required
@permission_required('product', 'create')
def product_variant_add(request, pk):
    """Fügt eine Variante zu einem Produkt hinzu."""
    product = get_object_or_404(Product, pk=pk)

    # Prüfen, ob das Produkt für Varianten konfiguriert ist
    if not product.has_variants:
        product.has_variants = True
        product.save()
        messages.info(request, 'Das Produkt wurde für Varianten aktiviert.')

    if request.method == 'POST':
        form = ProductVariantForm(request.POST)
        if form.is_valid():
            variant = form.save(commit=False)
            variant.parent_product = product
            variant.save()

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

                    # Versuchen, ein VariantWarehouse-Modell zu verwenden, falls vorhanden
                    try:
                        from inventory.models import VariantWarehouse

                        # Varianten-Lager-Eintrag erstellen
                        VariantWarehouse.objects.create(
                            variant=variant,
                            warehouse=warehouse,
                            quantity=initial_stock
                        )

                        # Optional: Bestandsbewegung erstellen, falls dein System dies unterstützt
                        try:
                            from inventory.models import VariantStockMovement
                            VariantStockMovement.objects.create(
                                variant=variant,
                                warehouse=warehouse,
                                quantity=initial_stock,
                                movement_type='in',
                                reference='Anfangsbestand',
                                created_by=request.user
                            )
                        except (ImportError, AttributeError):
                            # Keine Bewegung erstellen, wenn kein VariantStockMovement existiert
                            pass

                    except (ImportError, AttributeError):
                        # Wenn kein VariantWarehouse-Modell existiert, speichern wir den Bestand nicht
                        messages.warning(request, 'Bestandserfassung für Varianten ist nicht konfiguriert.')

                except Exception as e:
                    messages.error(request, f'Fehler bei der Erstellung des Anfangsbestands: {str(e)}')

            messages.success(request, 'Produktvariante wurde erfolgreich hinzugefügt.')
            return redirect('product_variants', pk=product.pk)
    else:
        # Name-Vorschlag generieren
        form = ProductVariantForm(initial={
            'name': product.name,
            'initial_stock': 0
        })

    context = {
        'product': product,
        'form': form,
    }

    return render(request, 'core/product/product_variant_form.html', context)


@login_required
@permission_required('product', 'edit')
def product_variant_update(request, pk, variant_id):
    product = get_object_or_404(Product, pk=pk)
    variant = get_object_or_404(ProductVariant, pk=variant_id, parent_product=product)

    context = handle_model_update(
        request,
        instance=variant,
        form_class=ProductVariantForm,
        model_name_singular='Produktvariante',
        success_redirect='product_variants',
        context_extra={'product': product, 'variant': variant}
    )

    return render(request, 'core/product/product_variant_form.html', context)


@login_required
@permission_required('product', 'delete')
def product_variant_delete(request, pk, variant_id):
    """Löscht eine Produktvariante."""
    product = get_object_or_404(Product, pk=pk)
    variant = get_object_or_404(ProductVariant, pk=variant_id, parent_product=product)

    if request.method == 'POST':
        variant.delete()
        messages.success(request, 'Produktvariante wurde erfolgreich gelöscht.')

        # Wenn keine Varianten mehr übrig sind, has_variants zurücksetzen
        if not product.variants.exists():
            product.has_variants = False
            product.save()

        return redirect('product_variants', pk=product.pk)

    context = {
        'product': product,
        'variant': variant,
    }

    return render(request, 'core/product/product_variant_confirm_delete.html', context)
