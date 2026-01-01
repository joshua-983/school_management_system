"""
Request Logging Middleware
Logs HTTP requests and responses for debugging and monitoring
"""
import logging
import time

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Start timer
        start_time = time.time()
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Log request
        logger.info(
            f"📥 Request: {request.method} {request.path} "
            f"| IP: {ip} "
            f"| User: {request.user if request.user.is_authenticated else 'Anonymous'}"
        )
        
        # Process request
        response = self.get_response(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"📤 Response: {response.status_code} "
            f"| Duration: {duration:.3f}s "
            f"| {request.method} {request.path}"
        )
        
        return response
    
    def process_exception(self, request, exception):
        """Log exceptions"""
        logger.error(
            f"🚨 Exception in {request.method} {request.path}: {exception}",
            exc_info=True
        )
        return None
