from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

def paginate_queryset(queryset, page, per_page=25):
    paginator = Paginator(queryset, per_page)
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)
