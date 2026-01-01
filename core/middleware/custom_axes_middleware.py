# core/middleware/custom_axes_middleware.py
"""
Custom Axes middleware that's async-compatible and satisfies Axes checks.
"""

import asyncio
from asgiref.sync import sync_to_async
from axes.middleware import AxesMiddleware as OriginalAxesMiddleware

class CustomAsyncAxesMiddleware(OriginalAxesMiddleware):
    """
    Custom Axes middleware that:
    1. Is async-compatible
    2. Satisfies Axes framework checks
    3. Can be directly referenced in settings
    """
    sync_capable = True
    async_capable = True
    
    async def __acall__(self, request):
        """Async call implementation"""
        if asyncio.iscoroutinefunction(self.get_response):
            response = await super().__call__(request)
        else:
            response = await sync_to_async(super().__call__)(request)
        return response
    
    def __call__(self, request):
        """Sync call that routes to async when needed"""
        if asyncio.iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        return super().__call__(request)