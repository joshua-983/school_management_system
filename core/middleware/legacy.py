# core/middleware/legacy.py
"""
Legacy Middleware Compatibility
Provides backward compatibility for old middleware patterns.
"""

import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class LegacyMiddlewareCompatibility(MiddlewareMixin):
    """
    Provides compatibility with legacy middleware patterns.
    This middleware handles any backward compatibility issues.
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        logger.debug("LegacyMiddlewareCompatibility initialized")
    
    def process_request(self, request):
        """Process request before view is called."""
        # Add any legacy request processing here
        return None
    
    def process_response(self, request, response):
        """Process response before it's sent to client."""
        # Add any legacy response processing here
        return response
    
    def process_exception(self, request, exception):
        """Process exceptions from views."""
        # Add any legacy exception handling here
        return None
    
    # Mark as async compatible
    async_capable = True
    sync_capable = True