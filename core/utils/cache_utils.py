"""
Cache utility functions for the InventoryPulse application.

This module provides helper functions for caching and cache invalidation,
including tenant-specific caching strategies.
"""
import hashlib
import logging
from functools import wraps

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete

from core.middleware import TenantMiddleware

logger = logging.getLogger('core')

# Cache timeouts (in seconds)
CACHE_TIMEOUT_SHORT = 60 * 5  # 5 minutes
CACHE_TIMEOUT_MEDIUM = 60 * 30  # 30 minutes
CACHE_TIMEOUT_LONG = 60 * 60 * 24  # 24 hours


def tenant_aware_cache_key(key_prefix, *args, **kwargs):
    """
    Generate a tenant-aware cache key.

    Args:
        key_prefix (str): The prefix for the cache key
        *args: Additional arguments to include in the key
        **kwargs: Additional keyword arguments to include in the key

    Returns:
        str: A tenant-aware cache key
    """
    # Get the current tenant
    tenant = TenantMiddleware.get_current_tenant()
    tenant_id = tenant.id if tenant else 'no_tenant'

    # Create a string representation of args and kwargs
    args_str = ':'.join(str(arg) for arg in args)
    kwargs_str = ':'.join(f"{k}={v}" for k, v in sorted(kwargs.items()))

    # Combine all parts
    key_parts = [key_prefix, f"tenant_{tenant_id}"]
    if args_str:
        key_parts.append(args_str)
    if kwargs_str:
        key_parts.append(kwargs_str)

    # Join with colons
    key = ':'.join(key_parts)

    # If the key is too long, hash it
    if len(key) > 250:
        key = f"{key_prefix}:tenant_{tenant_id}:{hashlib.md5(key.encode()).hexdigest()}"

    return key


def cached_result(timeout=CACHE_TIMEOUT_MEDIUM, key_prefix=None):
    """
    Decorator to cache the result of a function.

    Args:
        timeout (int): Cache timeout in seconds
        key_prefix (str): Prefix for the cache key. If None, uses the function name.

    Returns:
        function: Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate the cache key
            prefix = key_prefix or f"func_{func.__module__}.{func.__name__}"
            cache_key = tenant_aware_cache_key(prefix, *args, **kwargs)

            # Try to get the result from cache
            result = cache.get(cache_key)

            if result is None:
                # Cache miss, call the function
                result = func(*args, **kwargs)

                # Cache the result
                cache.set(cache_key, result, timeout)
                logger.debug(f"Cache miss for key: {cache_key}")
            else:
                logger.debug(f"Cache hit for key: {cache_key}")

            return result

        # Add a method to invalidate the cache for this function
        def invalidate_cache(*args, **kwargs):
            prefix = key_prefix or f"func_{func.__module__}.{func.__name__}"
            cache_key = tenant_aware_cache_key(prefix, *args, **kwargs)
            cache.delete(cache_key)
            logger.debug(f"Cache invalidated for key: {cache_key}")

        wrapper.invalidate_cache = invalidate_cache

        return wrapper

    return decorator


def invalidate_model_cache(sender, instance, **kwargs):
    """
    Invalidate cache for a model instance.

    Args:
        sender: The model class
        instance: The model instance
        **kwargs: Additional keyword arguments
    """
    model_name = sender.__name__.lower()
    cache_key_pattern = f"*{model_name}*{instance.pk}*"

    # Get all keys matching the pattern
    keys_to_delete = []
    for key in cache.keys(cache_key_pattern):
        keys_to_delete.append(key)

    # Delete the keys
    if keys_to_delete:
        cache.delete_many(keys_to_delete)
        logger.debug(f"Invalidated {len(keys_to_delete)} cache keys for {model_name} {instance.pk}")


def register_model_for_cache_invalidation(model):
    """
    Register a model for automatic cache invalidation on save and delete.

    Args:
        model: The model class to register
    """
    post_save.connect(invalidate_model_cache, sender=model)
    post_delete.connect(invalidate_model_cache, sender=model)
    logger.debug(f"Registered {model.__name__} for cache invalidation")


def clear_tenant_cache(tenant_id=None):
    """
    Clear all cache entries for a specific tenant.

    Args:
        tenant_id: The ID of the tenant. If None, uses the current tenant.
    """
    if tenant_id is None:
        tenant = TenantMiddleware.get_current_tenant()
        if tenant:
            tenant_id = tenant.id
        else:
            return  # No tenant to clear

    cache_key_pattern = f"*tenant_{tenant_id}*"

    # Get all keys matching the pattern
    keys_to_delete = []
    for key in cache.keys(cache_key_pattern):
        keys_to_delete.append(key)

    # Delete the keys
    if keys_to_delete:
        cache.delete_many(keys_to_delete)
        logger.debug(f"Cleared {len(keys_to_delete)} cache entries for tenant {tenant_id}")


def clear_all_tenant_caches():
    """
    Clear cache entries for all tenants.

    This is a more expensive operation and should be used sparingly.
    """
    from master_data.models.organisations_models import Organization

    # Get all active organizations
    organizations = Organization.objects.filter(is_active=True)

    total_keys_deleted = 0
    for org in organizations:
        cache_key_pattern = f"*tenant_{org.id}*"

        # Get all keys matching the pattern
        keys_to_delete = []
        for key in cache.keys(cache_key_pattern):
            keys_to_delete.append(key)

        # Delete the keys
        if keys_to_delete:
            cache.delete_many(keys_to_delete)
            total_keys_deleted += len(keys_to_delete)
            logger.debug(f"Cleared {len(keys_to_delete)} cache entries for tenant {org.id}")

    logger.info(f"Cleared a total of {total_keys_deleted} cache entries across all tenants")
    return total_keys_deleted


# Register models for cache invalidation
def register_models():
    """Register all models that should have automatic cache invalidation."""
    from module_management.models import Module, FeatureFlag, SubscriptionPackage, Subscription
    from master_data.models.organisations_models import Organization, Department

    models_to_register = [
        Module,
        FeatureFlag,
        SubscriptionPackage,
        Subscription,
        Organization,
        Department,
    ]

    for model in models_to_register:
        register_model_for_cache_invalidation(model)
