import logging

logger = logging.getLogger(__name__)


def log_list_view_usage(request, view_name, filters=None, sort_by=None, page=None, extra_context=None):
    """
    Einheitliches Logging für Listenansichten.

    :param request: HttpRequest-Objekt
    :param view_name: Name der View (z.B. 'user_management')
    :param filters: dict mit Filterparametern
    :param sort_by: sortierkriterium (z.B. 'username' oder '-created_at')
    :param page: aktuelle Seite
    :param extra_context: optionale zusätzliche Informationen (als dict)
    """
    user = request.user if request.user.is_authenticated else 'Anonymous'
    log_data = {
        'user': str(user),
        'view': view_name,
        'filters': filters or {},
        'sort_by': sort_by,
        'page': page,
        'extra': extra_context or {},
        'method': request.method,
        'path': request.get_full_path()
    }
    logger.info(f"ListView accessed: {log_data}")
