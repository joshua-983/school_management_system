# core/middleware/async_auth_middleware.py
"""
Async-compatible wrapper for Django's authentication middleware
to prevent SynchronousOnlyOperation errors in ASGI context.
"""
from asgiref.sync import sync_to_async
from django.contrib.auth.middleware import AuthenticationMiddleware as BaseAuthMiddleware
from django.contrib.auth import get_user
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

class AsyncAuthenticationMiddleware(MiddlewareMixin):
    """
    Async-compatible authentication middleware that wraps Django's 
    standard auth middleware with async support.
    """
    sync_capable = True
    async_capable = True
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.base_auth_middleware = BaseAuthMiddleware(get_response)
    
    async def __call__(self, request):
        """Async call handler"""
        # Process authentication asynchronously
        await self.process_request_async(request)
        response = await self.get_response(request)
        return response
    
    async def process_request_async(self, request):
        """Async version of authentication setup"""
        try:
            # Use sync_to_async to wrap the synchronous auth setup
            user = await sync_to_async(get_user)(request)
            request.user = user
            
            # Also set up the lazy wrapper for compatibility
            if not hasattr(request.user, '_setup'):
                from django.utils.functional import SimpleLazyObject
                request.user = SimpleLazyObject(lambda: user)
                
        except Exception as e:
            logger.error(f"Auth middleware error: {str(e)}")
            from django.contrib.auth.models import AnonymousUser
            request.user = AnonymousUser()