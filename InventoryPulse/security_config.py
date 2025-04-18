"""
Security configuration for InventoryPulse

This file contains security-related settings that should be kept separate from
the main settings.py file for better security. In a production environment,
this file should have restricted access permissions.
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# IP addresses allowed to access the superadmin area
# In production, this should be a list of specific IP addresses
SUPERADMIN_ALLOWED_IPS = ['127.0.0.1', '::1']  # Default: localhost only

# Session timeout for superadmin area (in seconds)
# 15 minutes (900 seconds) is a good balance between security and usability
SUPERADMIN_SESSION_TIMEOUT = 15 * 60  # 15 minutes

# Rate limiting settings for login attempts
LOGIN_RATE_LIMIT = {
    'attempts': 5,  # Number of attempts allowed
    'timeframe': 5 * 60,  # Timeframe in seconds (5 minutes)
    'lockout_time': 30 * 60  # Lockout time in seconds (30 minutes)
}

# Load environment-specific settings if available
env_config = os.environ.get('INVENTORY_PULSE_SECURITY_CONFIG')
if env_config and os.path.exists(env_config):
    with open(env_config, 'r') as f:
        exec(f.read())