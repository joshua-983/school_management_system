# core/middleware/error_handling.py
import logging
from django.http import HttpResponseServerError
from django.template import loader

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            logger.error(f"Unhandled exception: {e}")
            return HttpResponseServerError("Internal Server Error")
    
    # Mark as async capable
    async_capable = True
    sync_capable = True
    
    async def __acall__(self, request):
        """Async version for ASGI"""
        try:
            response = await self.get_response(request)
            return response
        except Exception as e:
            logger.error(f"Unhandled exception in async: {e}")
            return HttpResponseServerError("Internal Server Error")