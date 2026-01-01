# core/middleware/async_session_middleware.py
"""
Async-compatible wrapper for Django's session middleware.
"""
from asgiref.sync import sync_to_async
from django.contrib.sessions.middleware import SessionMiddleware as BaseSessionMiddleware
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

class AsyncSessionMiddleware(MiddlewareMixin):
    """
    Async-compatible session middleware that wraps Django's 
    standard session middleware with async support.
    """
    sync_capable = True
    async_capable = True
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.base_session_middleware = BaseSessionMiddleware(get_response)
    
    async def __call__(self, request):
        """Async call handler"""
        try:
            # Load session asynchronously
            await sync_to_async(self.base_session_middleware.process_request)(request)
            response = await self.get_response(request)
            # Save session asynchronously
            await sync_to_async(self.base_session_middleware.process_response)(request, response)
            return response
        except Exception as e:
            logger.error(f"Session middleware error: {str(e)}")
            # Continue without session
            response = await self.get_response(request)
            return response