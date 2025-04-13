import mimetypes
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http.response import JsonResponse, Http404, FileResponse
from django.shortcuts import get_object_or_404, render, redirect

from core.utils.deletion import handle_delete_view
from core.utils.files import delete_file_if_exists
from core.utils.forms import handle_form_view
from core.utils.view_helpers import handle_model_delete
from product_management.forms.product_forms import ProductPhotoForm, ProductAttachmentForm
from product_management.models.products import ProductPhoto, ProductAttachment, Product


@login_required
@permission_required('products.view_product', raise_exception=True)
def product_photos(request, pk):
    """Zeigt alle Fotos eines Produkts an."""
    product = get_object_or_404(Product, pk=pk)
    photos = product.photos.all()

    context = {
        'product': product,
        'photos': photos,
    }

    return render(request, 'core/product/product_photos.html', context)


@login_required
@permission_required('product', 'edit')
def product_photo_add(request, pk):
    product = get_object_or_404(Product, pk=pk)

    def form_instance_save(form):
        photo = form.save(commit=False)
        photo.product = product
        photo.save()
        messages.success(request, 'Foto wurde erfolgreich hinzugefügt.')
        return redirect('product_photos', pk=product.pk)

    return handle_form_view(
        request,
        form_class=ProductPhotoForm,
        template='core/product/product_photo_form.html',
        redirect_url=f'/produkte/{pk}/fotos',  # oder benutze reverse()
        context_extra={'product': product}
    )


@login_required
@permission_required('product', 'delete')
def product_photo_delete(request, pk, photo_id):
    product = get_object_or_404(Product, pk=pk)
    photo = get_object_or_404(ProductPhoto, pk=photo_id, product=product)

    return handle_delete_view(
        request,
        obj=photo,
        redirect_url='product_photos',  # oder f'/produkte/{pk}/fotos'
        confirm_template='core/product/product_photo_confirm_delete.html',
        context={'product': product, 'photo': photo},
        filefield=photo.image,
        delete_file_func=delete_file_if_exists
    )


@login_required
@permission_required('product', 'edit')
def product_photo_set_primary(request, pk, photo_id):
    """Setzt ein Foto als Hauptfoto des Produkts."""
    product = get_object_or_404(Product, pk=pk)
    photo = get_object_or_404(ProductPhoto, pk=photo_id, product=product)

    # Erst alle anderen Fotos als nicht-primär markieren
    ProductPhoto.objects.filter(product=product).update(is_primary=False)

    # Dann dieses Foto als primär markieren
    photo.is_primary = True
    photo.save()

    messages.success(request, 'Hauptfoto wurde erfolgreich gesetzt.')

    # AJAX-Request oder normale Anfrage unterscheiden
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    else:
        return redirect('product_photos', pk=product.pk)


# ------------------------------------------------------------------------------
# Produktanhänge
# ------------------------------------------------------------------------------

@login_required
@permission_required('products.view_product', raise_exception=True)
def product_attachments(request, pk):
    """Zeigt alle Anhänge eines Produkts an."""
    product = get_object_or_404(Product, pk=pk)
    attachments = product.attachments.all()

    context = {
        'product': product,
        'attachments': attachments,
    }

    return render(request, 'core/product/product_attachments.html', context)


@login_required
@permission_required('product', 'edit')
def product_attachment_add(request, pk):
    """Fügt einen Anhang zu einem Produkt hinzu."""
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.product = product
            attachment.save()

            messages.success(request, 'Anhang wurde erfolgreich hinzugefügt.')
            return redirect('product_attachments', pk=product.pk)
    else:
        form = ProductAttachmentForm()

    context = {
        'product': product,
        'form': form,
    }

    return render(request, 'core/product/product_attachment_form.html', context)


@login_required
@permission_required('product', 'delete')
def product_attachment_delete(request, pk, attachment_id):
    product = get_object_or_404(Product, pk=pk)
    attachment = get_object_or_404(ProductAttachment, pk=attachment_id, product=product)

    # Datei löschen
    if request.method == 'POST' and attachment.file and os.path.isfile(attachment.file.path):
        os.remove(attachment.file.path)

    context = handle_model_delete(
        request,
        instance=attachment,
        model_name_singular='Anhang',
        success_redirect='product_attachments',
        context_extra={'product': product}
    )

    return render(request, 'core/product/product_attachment_confirm_delete.html', context)


@login_required
@permission_required('products.view_product', raise_exception=True)
def product_attachment_download(request, pk, attachment_id):
    """Lädt einen Produktanhang herunter."""
    product = get_object_or_404(Product, pk=pk)
    attachment = get_object_or_404(ProductAttachment, pk=attachment_id, product=product)

    if not attachment.file:
        raise Http404("Die angeforderte Datei existiert nicht.")

    file_path = attachment.file.path

    if not os.path.exists(file_path):
        raise Http404("Die angeforderte Datei existiert nicht.")

    # Mime-Type bestimmen
    content_type, encoding = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'application/octet-stream'

    # Datei öffnen und als Response senden
    try:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response
    except Exception as e:
        messages.error(request, f"Fehler beim Herunterladen der Datei: {str(e)}")
        return redirect('product_attachments', pk=product.pk)
