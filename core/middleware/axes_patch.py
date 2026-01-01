# core/middleware/axes_patch.py
"""
Patch to make Axes framework recognize our async-wrapped middleware.
"""

def patch_axes_middleware_check():
    """
    Monkey-patch Axes to recognize our async-wrapped middleware.
    """
    try:
        from axes.checks import AxesCheck
        from django.conf import settings
        
        # Save original check method
        original_check = AxesCheck.check
        
        # Create patched version
        def patched_check(cls, app_configs=None, **kwargs):
            # Call original check
            errors = original_check(app_configs, **kwargs)
            
            # Check if the error is about missing middleware
            for i, error in enumerate(errors):
                if error.id == 'axes.W002' and 'AxesMiddleware' in error.msg:
                    # Check if we have the async-wrapped version
                    has_wrapped_middleware = any(
                        'make_middleware_async("axes.middleware.AxesMiddleware")' in mw 
                        for mw in settings.MIDDLEWARE
                    )
                    
                    if has_wrapped_middleware:
                        # Remove the warning since we have the wrapped version
                        errors.pop(i)
                        break
            
            return errors
        
        # Apply the patch
        AxesCheck.check = classmethod(patched_check)
        print("✅ Patched Axes middleware check")
        
    except ImportError as e:
        print(f"⚠️  Could not patch Axes: {e}")

# Apply patch when module is imported
patch_axes_middleware_check()