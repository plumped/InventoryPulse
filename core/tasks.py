"""
Asynchronous tasks for the InventoryPulse application.

This module defines Celery tasks for common operations that should be
performed asynchronously.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from core.middleware import tenant_context
from core.utils.cache_utils import clear_tenant_cache

logger = logging.getLogger('core')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, subject, message, from_email, recipient_list, html_message=None):
    """
    Send an email asynchronously.
    
    Args:
        subject: Email subject
        message: Email message (plain text)
        from_email: Sender email address
        recipient_list: List of recipient email addresses
        html_message: HTML version of the message (optional)
        
    Returns:
        int: Number of emails sent
    """
    try:
        logger.info(f"Sending email to {recipient_list}")
        return send_mail(
            subject=subject,
            message=message,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
    except Exception as exc:
        logger.error(f"Error sending email: {str(exc)}")
        raise self.retry(exc=exc)


@shared_task(bind=True)
def clear_tenant_cache_task(self, tenant_id=None):
    """
    Clear the cache for a specific tenant.
    
    Args:
        tenant_id: ID of the tenant to clear cache for. If None, clears all tenant caches.
    """
    try:
        if tenant_id:
            logger.info(f"Clearing cache for tenant {tenant_id}")
            clear_tenant_cache(tenant_id)
        else:
            logger.info("Clearing all tenant caches")
            # This would need to be implemented in cache_utils.py
            from core.utils.cache_utils import clear_all_tenant_caches
            clear_all_tenant_caches()
        return True
    except Exception as exc:
        logger.error(f"Error clearing tenant cache: {str(exc)}")
        return False


@shared_task(bind=True)
def process_data_import(self, import_id, tenant_id=None):
    """
    Process a data import asynchronously.
    
    Args:
        import_id: ID of the import to process
        tenant_id: ID of the tenant the import belongs to
    """
    try:
        logger.info(f"Processing data import {import_id} for tenant {tenant_id}")
        
        # If tenant_id is provided, set the tenant context
        if tenant_id:
            @tenant_context(tenant_id)
            def _process_import():
                from data_operations.models import DataImport
                from data_operations.services import import_service
                
                # Get the import
                data_import = DataImport.objects.get(id=import_id)
                
                # Update status
                data_import.status = 'processing'
                data_import.started_at = timezone.now()
                data_import.save(update_fields=['status', 'started_at'])
                
                try:
                    # Process the import
                    result = import_service.process_import(data_import)
                    
                    # Update status
                    data_import.status = 'completed'
                    data_import.completed_at = timezone.now()
                    data_import.result = result
                    data_import.save(update_fields=['status', 'completed_at', 'result'])
                    
                    return True
                except Exception as e:
                    # Update status
                    data_import.status = 'failed'
                    data_import.error_message = str(e)
                    data_import.completed_at = timezone.now()
                    data_import.save(update_fields=['status', 'error_message', 'completed_at'])
                    
                    logger.error(f"Error processing import {import_id}: {str(e)}")
                    raise
            
            return _process_import()
        else:
            logger.error(f"No tenant ID provided for import {import_id}")
            return False
    except Exception as exc:
        logger.error(f"Error processing data import: {str(exc)}")
        return False


@shared_task(bind=True)
def generate_report(self, report_id, tenant_id=None, user_id=None):
    """
    Generate a report asynchronously.
    
    Args:
        report_id: ID of the report to generate
        tenant_id: ID of the tenant the report belongs to
        user_id: ID of the user who requested the report
    """
    try:
        logger.info(f"Generating report {report_id} for tenant {tenant_id}")
        
        # If tenant_id is provided, set the tenant context
        if tenant_id:
            @tenant_context(tenant_id)
            def _generate_report():
                from analytics.models import Report
                from analytics.services import report_service
                from django.contrib.auth.models import User
                
                # Get the report
                report = Report.objects.get(id=report_id)
                
                # Get the user if provided
                user = None
                if user_id:
                    user = User.objects.get(id=user_id)
                
                # Update status
                report.status = 'processing'
                report.started_at = timezone.now()
                report.save(update_fields=['status', 'started_at'])
                
                try:
                    # Generate the report
                    result = report_service.generate_report(report, user)
                    
                    # Update status
                    report.status = 'completed'
                    report.completed_at = timezone.now()
                    report.result = result
                    report.save(update_fields=['status', 'completed_at', 'result'])
                    
                    # Send notification email if user provided
                    if user and user.email:
                        send_email_task.delay(
                            subject=f"Report {report.name} is ready",
                            message=f"Your report {report.name} has been generated and is ready to view.",
                            from_email=None,
                            recipient_list=[user.email]
                        )
                    
                    return True
                except Exception as e:
                    # Update status
                    report.status = 'failed'
                    report.error_message = str(e)
                    report.completed_at = timezone.now()
                    report.save(update_fields=['status', 'error_message', 'completed_at'])
                    
                    logger.error(f"Error generating report {report_id}: {str(e)}")
                    raise
            
            return _generate_report()
        else:
            logger.error(f"No tenant ID provided for report {report_id}")
            return False
    except Exception as exc:
        logger.error(f"Error generating report: {str(exc)}")
        return False