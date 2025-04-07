from django.shortcuts import render, redirect

def handle_delete_view(request, obj, redirect_url, confirm_template, context=None, filefield=None, delete_file_func=None):
    if request.method == 'POST':
        if filefield and delete_file_func:
            delete_file_func(filefield)
        obj.delete()
        return redirect(redirect_url)

    return render(request, confirm_template, context or {})
