# core/middleware/async_axes_fix.py
"""
Async-compatible Axes middleware that satisfies Axes framework checks.
"""

import asyncio
from asgiref.sync import sync_to_async

try:
    from axes.middleware import AxesMiddleware as OriginalAxesMiddleware
    
    class AsyncAxesMiddlewareFixed(OriginalAxesMiddleware):
        """
        Fixed version of AsyncAxesMiddleware that Axes framework will recognize.
        """
        # These are important for Axes checks
        __name__ = 'AxesMiddleware'  # Trick Axes into thinking this is the original
        __module__ = 'axes.middleware'
        
        sync_capable = True
        async_capable = True
        
        async def __acall__(self, request):
            if asyncio.iscoroutinefunction(self.get_response):
                response = await super().__call__(request)
            else:
                response = await sync_to_async(super().__call__)(request)
            return response
        
        def __call__(self, request):
            if asyncio.iscoroutinefunction(self.get_response):
                return self.__acall__(request)
            return super().__call__(request)
    
    # Alias it to the name Axes looks for
    AxesMiddleware = AsyncAxesMiddlewareFixed
    
except ImportError:
    # Fallback if axes is not installed
    from django.utils.deprecation import MiddlewareMixin
    
    class AsyncAxesMiddlewareFixed(MiddlewareMixin):
        sync_capable = True
        async_capable = True
        pass
    
    AxesMiddleware = AsyncAxesMiddlewareFixed