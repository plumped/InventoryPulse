import base64
import logging

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings

logger = logging.getLogger('core')

# Get the encryption key from settings or generate a new one
ENCRYPTION_KEY = getattr(settings, 'ENCRYPTION_KEY', None)
if not ENCRYPTION_KEY:
    # If no key is provided, use the SECRET_KEY with a salt to derive a key
    salt = b'InventoryPulse_salt_for_encryption'  # This should ideally be stored securely
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    ENCRYPTION_KEY = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))

# Initialize the Fernet cipher with the key
try:
    cipher_suite = Fernet(ENCRYPTION_KEY)
except Exception as e:
    logger.error(f"Failed to initialize encryption: {str(e)}")
    # Fallback to a new key if the provided one is invalid
    cipher_suite = Fernet(Fernet.generate_key())

def encrypt_text(text):
    """
    Encrypt a text string.
    
    Args:
        text (str): The text to encrypt
        
    Returns:
        str: The encrypted text as a base64-encoded string
    """
    if not text:
        return text
    
    try:
        # Convert to bytes if it's a string
        if isinstance(text, str):
            text = text.encode()
        
        # Encrypt the text
        encrypted_text = cipher_suite.encrypt(text)
        
        # Return as a base64-encoded string
        return base64.urlsafe_b64encode(encrypted_text).decode()
    except Exception as e:
        logger.error(f"Encryption error: {str(e)}")
        return None

def decrypt_text(encrypted_text):
    """
    Decrypt an encrypted text string.
    
    Args:
        encrypted_text (str): The encrypted text as a base64-encoded string
        
    Returns:
        str: The decrypted text
    """
    if not encrypted_text:
        return encrypted_text
    
    try:
        # Decode from base64
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_text)
        
        # Decrypt the text
        decrypted_bytes = cipher_suite.decrypt(encrypted_bytes)
        
        # Return as a string
        return decrypted_bytes.decode()
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}")
        return None

class EncryptedTextField:
    """
    A descriptor for encrypted text fields.
    This can be used to automatically encrypt and decrypt text fields in models.
    
    Usage:
        class MyModel(models.Model):
            _sensitive_data = models.TextField()
            sensitive_data = EncryptedTextField('_sensitive_data')
    """
    def __init__(self, field_name):
        self.field_name = field_name
    
    def __get__(self, instance, owner):
        if instance is None:
            return self
        
        encrypted_value = getattr(instance, self.field_name)
        if encrypted_value:
            return decrypt_text(encrypted_value)
        return None
    
    def __set__(self, instance, value):
        if value is not None:
            encrypted_value = encrypt_text(value)
            setattr(instance, self.field_name, encrypted_value)
        else:
            setattr(instance, self.field_name, None)