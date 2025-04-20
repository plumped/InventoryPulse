import logging

from .error_handling import get_current_request_id


class RequestIDLogFormatter(logging.Formatter):
    """
    Custom log formatter that includes the request ID in each log message.
    """
    def format(self, record):
        # Add request_id to the record if not already present
        if not hasattr(record, 'request_id'):
            record.request_id = get_current_request_id() or 'no-request-id'
        
        # Format the record
        return super().format(record)