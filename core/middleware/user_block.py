"""
User Block Middleware
"""
from django.http import HttpResponseForbidden

class UserBlockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Check if user is blocked
            if hasattr(request.user, 'is_blocked') and request.user.is_blocked:
                return HttpResponseForbidden("Your account has been blocked")
        return self.get_response(request)
