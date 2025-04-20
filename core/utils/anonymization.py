import hashlib
import logging
import random
import re
import string
from datetime import datetime, timedelta

logger = logging.getLogger('core')

def anonymize_email(email):
    """
    Anonymize an email address while preserving the domain.
    
    Args:
        email (str): The email address to anonymize
        
    Returns:
        str: The anonymized email address
    """
    if not email or '@' not in email:
        return email
    
    try:
        username, domain = email.split('@', 1)
        
        # Hash the username
        hashed = hashlib.sha256(username.encode()).hexdigest()[:8]
        
        return f"anon_{hashed}@{domain}"
    except Exception as e:
        logger.error(f"Error anonymizing email: {str(e)}")
        return email

def anonymize_name(name):
    """
    Anonymize a name by replacing it with a random name.
    
    Args:
        name (str): The name to anonymize
        
    Returns:
        str: The anonymized name
    """
    if not name:
        return name
    
    try:
        # Generate a random name of similar length
        length = max(4, min(len(name), 10))
        random_name = ''.join(random.choices(string.ascii_letters, k=length))
        
        return f"Anon_{random_name}"
    except Exception as e:
        logger.error(f"Error anonymizing name: {str(e)}")
        return name

def anonymize_phone(phone):
    """
    Anonymize a phone number by keeping only the last 4 digits.
    
    Args:
        phone (str): The phone number to anonymize
        
    Returns:
        str: The anonymized phone number
    """
    if not phone:
        return phone
    
    try:
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Keep only the last 4 digits
        if len(digits) > 4:
            return f"XXX-XXX-{digits[-4:]}"
        else:
            return "XXX-XXX-XXXX"
    except Exception as e:
        logger.error(f"Error anonymizing phone: {str(e)}")
        return phone

def anonymize_address(address):
    """
    Anonymize an address by replacing specific parts.
    
    Args:
        address (str): The address to anonymize
        
    Returns:
        str: The anonymized address
    """
    if not address:
        return address
    
    try:
        # Replace house/building number with XXX
        anonymized = re.sub(r'^\d+', 'XXX', address)
        
        # Replace apartment/unit numbers
        anonymized = re.sub(r'(apt|unit|suite|#)\s*\d+', r'\1 XXX', anonymized, flags=re.IGNORECASE)
        
        return anonymized
    except Exception as e:
        logger.error(f"Error anonymizing address: {str(e)}")
        return address

def anonymize_credit_card(cc_number):
    """
    Anonymize a credit card number by keeping only the last 4 digits.
    
    Args:
        cc_number (str): The credit card number to anonymize
        
    Returns:
        str: The anonymized credit card number
    """
    if not cc_number:
        return cc_number
    
    try:
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', cc_number)
        
        # Keep only the last 4 digits
        if len(digits) > 4:
            return f"XXXX-XXXX-XXXX-{digits[-4:]}"
        else:
            return "XXXX-XXXX-XXXX-XXXX"
    except Exception as e:
        logger.error(f"Error anonymizing credit card: {str(e)}")
        return cc_number

def anonymize_date(date, max_days_offset=30):
    """
    Anonymize a date by adding or subtracting a random number of days.
    
    Args:
        date (datetime): The date to anonymize
        max_days_offset (int): Maximum number of days to offset the date
        
    Returns:
        datetime: The anonymized date
    """
    if not date:
        return date
    
    try:
        # Add or subtract a random number of days
        days_offset = random.randint(-max_days_offset, max_days_offset)
        return date + timedelta(days=days_offset)
    except Exception as e:
        logger.error(f"Error anonymizing date: {str(e)}")
        return date

def anonymize_ip(ip_address):
    """
    Anonymize an IP address by replacing the last octet with zeros.
    
    Args:
        ip_address (str): The IP address to anonymize
        
    Returns:
        str: The anonymized IP address
    """
    if not ip_address:
        return ip_address
    
    try:
        # Check if it's an IPv4 address
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_address):
            parts = ip_address.split('.')
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0"
        
        # For IPv6, replace the last 64 bits
        elif ':' in ip_address:
            parts = ip_address.split(':')
            if len(parts) > 4:
                return ':'.join(parts[:4]) + ':0:0:0:0'
        
        return ip_address
    except Exception as e:
        logger.error(f"Error anonymizing IP address: {str(e)}")
        return ip_address

def anonymize_text(text, sensitive_patterns=None):
    """
    Anonymize text by replacing sensitive patterns.
    
    Args:
        text (str): The text to anonymize
        sensitive_patterns (list): List of regex patterns to anonymize
        
    Returns:
        str: The anonymized text
    """
    if not text:
        return text
    
    try:
        # Default patterns to anonymize
        default_patterns = [
            # Credit card numbers
            (r'\b(?:\d[ -]*?){13,16}\b', 'XXXX-XXXX-XXXX-XXXX'),
            # Social Security Numbers
            (r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', 'XXX-XX-XXXX'),
            # Email addresses
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', lambda m: anonymize_email(m.group(0))),
            # Phone numbers
            (r'\b(?:\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b', lambda m: anonymize_phone(m.group(0))),
        ]
        
        # Combine with custom patterns
        patterns = default_patterns + (sensitive_patterns or [])
        
        # Apply all patterns
        result = text
        for pattern, replacement in patterns:
            if callable(replacement):
                result = re.sub(pattern, replacement, result)
            else:
                result = re.sub(pattern, replacement, result)
        
        return result
    except Exception as e:
        logger.error(f"Error anonymizing text: {str(e)}")
        return text

class AnonymizedExport:
    """
    A class for creating anonymized exports of data.
    
    Usage:
        exporter = AnonymizedExport()
        anonymized_data = exporter.anonymize_queryset(
            queryset,
            anonymize_fields={
                'email': anonymize_email,
                'name': anonymize_name,
                'phone': anonymize_phone,
                'address': anonymize_address,
                'credit_card': anonymize_credit_card,
            }
        )
    """
    def anonymize_queryset(self, queryset, anonymize_fields=None, exclude_fields=None):
        """
        Anonymize a queryset for export.
        
        Args:
            queryset: The queryset to anonymize
            anonymize_fields (dict): Mapping of field names to anonymization functions
            exclude_fields (list): Fields to exclude from the export
            
        Returns:
            list: A list of dictionaries with anonymized data
        """
        if not queryset:
            return []
        
        # Default fields to exclude
        default_exclude = ['password', 'secret', 'token', 'key']
        exclude_fields = (exclude_fields or []) + default_exclude
        
        # Default anonymization functions
        default_anonymize = {
            'email': anonymize_email,
            'mail': anonymize_email,
            'name': anonymize_name,
            'first_name': anonymize_name,
            'last_name': anonymize_name,
            'phone': anonymize_phone,
            'telephone': anonymize_phone,
            'mobile': anonymize_phone,
            'address': anonymize_address,
            'street': anonymize_address,
            'credit_card': anonymize_credit_card,
            'cc_number': anonymize_credit_card,
            'ip': anonymize_ip,
            'ip_address': anonymize_ip,
        }
        
        # Combine with custom anonymization functions
        anonymize_fields = {**default_anonymize, **(anonymize_fields or {})}
        
        result = []
        for obj in queryset:
            # Convert model instance to dictionary
            if hasattr(obj, '__dict__'):
                data = obj.__dict__.copy()
                # Remove private fields
                data = {k: v for k, v in data.items() if not k.startswith('_')}
            else:
                data = dict(obj)
            
            # Exclude specified fields
            for field in exclude_fields:
                if field in data:
                    del data[field]
            
            # Anonymize fields
            for field, anonymize_func in anonymize_fields.items():
                if field in data and data[field]:
                    data[field] = anonymize_func(data[field])
            
            result.append(data)
        
        return result