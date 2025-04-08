import logging

def log_test():
    app_loggers = [
        'admin_dashboard', 'core', 'inventory', 'order', 'suppliers',
        'rma', 'organization', 'accessmanagement', 'api',
        'interfaces', 'documents'
    ]

    for app in app_loggers:
        logger = logging.getLogger(app)
        logger.debug(f"[{app}] DEBUG test message")
        logger.info(f"[{app}] INFO test message")
        logger.warning(f"[{app}] WARNING test message")
        logger.error(f"[{app}] ERROR test message")

    # Django und django.request separat
    logging.getLogger('django').info("[django] INFO message")
    logging.getLogger('django.request').error("[django.request] ERROR message")

    print("✅ Logging test messages sent.")
