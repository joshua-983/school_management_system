import logging
from django.contrib.auth.models import AnonymousUser

class UserContextFilter(logging.Filter):
    """
    Custom filter to add user context to log records.
    """
    
    def filter(self, record):
        try:
            # Try to get the current request from thread local
            from django.utils.deprecation import MiddlewareMixin
            import threading
            
            # Get request from thread local (common pattern)
            request = getattr(threading.local(), 'request', None)
            
            if request and hasattr(request, 'user'):
                user = request.user
                if user.is_authenticated:
                    record.user_id = user.id
                    record.username = user.get_username()
                else:
                    record.user_id = 'anonymous'
                    record.username = 'anonymous'
            else:
                # Fallback if no request context
                record.user_id = 'none'
                record.username = 'none'
                
        except Exception as e:
            # Safe fallback if anything goes wrong
            record.user_id = 'error'
            record.username = 'error'
            record.filter_error = str(e)
        
        return True