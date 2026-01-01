# core/middleware/async_patches.py - FIXED VERSION
"""
Async middleware compatibility layer.
Avoid importing Django models at module level to prevent circular imports.
"""
import asyncio
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Minimal version - don't import Django models here
def make_middleware_async(middleware_class):
    """
    Convert synchronous middleware to async.
    This is called lazily when middleware is instantiated.
    """
    @wraps(middleware_class)
    class AsyncMiddleware:
        def __init__(self, get_response):
            self.get_response = get_response
            self.sync_middleware = middleware_class(get_response)
            
        async def __call__(self, request):
            # Handle the request with the sync middleware
            response = self.sync_middleware(request)
            return response
            
        def async_capable(self):
            return True
            
        def sync_capable(self):
            return True
    
    return AsyncMiddleware

# Don't create pre-made async middleware wrappers here
# Let Django handle it automatically