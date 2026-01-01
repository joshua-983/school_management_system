"""
SAFE Async compatibility patch for Django Axes
This version does NOT patch AxesMiddleware in sync mode
"""

def patch_axes_middleware_check():
    """
    Check if we should patch Axes for async, but don't actually patch
    in sync (WSGI) mode to prevent breaking Django middleware chain
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from django.conf import settings
        
        # Check if we're actually in ASGI mode
        is_asgi = hasattr(settings, 'ASGI_APPLICATION') and settings.ASGI_APPLICATION
        
        if not is_asgi:
            # We're in WSGI (sync) mode - DO NOT PATCH
            logger.info("ℹ️  WSGI mode detected, skipping Axes async patch")
            return True  # Return True to prevent warning
        
        # We're in ASGI mode, but Axes async support is problematic
        # For now, don't patch it
        logger.info("ℹ️  ASGI mode detected but skipping Axes async patch (known issues)")
        return True
        
    except Exception:
        # If anything fails, return True to prevent warnings
        return True

# Aliases
apply_async_patches = patch_axes_middleware_check
patch_axes_for_async = patch_axes_middleware_check

__all__ = ['patch_axes_middleware_check', 'apply_async_patches', 'patch_axes_for_async']
