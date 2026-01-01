"""
Rate Limiting Middleware
"""
import time
from django.core.cache import cache
from django.http import HttpResponseForbidden

class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Simple rate limiting by IP
        ip = request.META.get('REMOTE_ADDR', '')
        if ip:
            key = f'rate_limit:{ip}'
            requests = cache.get(key, [])
            
            # Remove requests older than 1 minute
            current_time = time.time()
            requests = [req_time for req_time in requests if current_time - req_time < 60]
            
            # Check if over limit (100 requests per minute)
            if len(requests) >= 100:
                return HttpResponseForbidden("Rate limit exceeded")
            
            # Add current request
            requests.append(current_time)
            cache.set(key, requests, 60)
        
        return self.get_response(request)
