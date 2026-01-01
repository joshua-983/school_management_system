# core/middleware/async_wrapper.py
import asyncio
from asgiref.sync import sync_to_async
from django.utils.deprecation import MiddlewareMixin
from django.utils.module_loading import import_string

def make_middleware_async(middleware_path):
    """
    Factory function to create async-compatible middleware from a path string.
    Usage in settings.py: 'core.middleware.make_middleware_async("path.to.MiddlewareClass")'
    """
    def middleware_factory(get_response):
        # Import the actual middleware class
        middleware_class = import_string(middleware_path)
        
        # Check if it's already async-capable
        if hasattr(middleware_class, 'async_capable') and middleware_class.async_capable:
            return middleware_class(get_response)
        
        # Create async wrapper class
        class AsyncMiddlewareWrapper(MiddlewareMixin):
            sync_capable = True
            async_capable = True
            
            def __init__(self, get_response):
                self.get_response = get_response
                self.wrapped = middleware_class(get_response)
                
            def __call__(self, request):
                if asyncio.iscoroutinefunction(self.get_response):
                    return self.__acall__(request)
                return self.wrapped(request)
            
            async def __acall__(self, request):
                response = await sync_to_async(self.wrapped)(request)
                if asyncio.iscoroutine(response):
                    response = await response
                return response
        
        return AsyncMiddlewareWrapper(get_response)
    
    return middleware_factory


def wrap_django_middleware(middleware_path):
    """Wrapper for Django's built-in middleware that might have async issues"""
    def middleware_factory(get_response):
        middleware_class = import_string(middleware_path)
        
        class WrappedDjangoMiddleware(MiddlewareMixin):
            sync_capable = True
            async_capable = True
            
            def __init__(self, get_response):
                self.get_response = get_response
                self.wrapped = middleware_class(get_response)
                
            def __call__(self, request):
                if asyncio.iscoroutinefunction(self.get_response):
                    return self.__acall__(request)
                return self.wrapped(request)
            
            async def __acall__(self, request):
                try:
                    response = await sync_to_async(self.wrapped)(request)
                    if asyncio.iscoroutine(response):
                        response = await response
                    return response
                except Exception as e:
                    print(f"Error in wrapped Django middleware {middleware_path}: {str(e)}")
                    from django.http import HttpResponseServerError
                    return HttpResponseServerError("Internal Server Error")
        
        return WrappedDjangoMiddleware(get_response)
    
    return middleware_factory