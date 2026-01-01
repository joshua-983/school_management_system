"""
Session Timeout Middleware
"""
import time
from django.contrib.auth import logout
from django.conf import settings

class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Check session expiry
            last_activity = request.session.get('last_activity')
            if last_activity:
                current_time = time.time()
                timeout = getattr(settings, 'SESSION_COOKIE_AGE', 1209600)
                if current_time - last_activity > timeout:
                    logout(request)
            request.session['last_activity'] = time.time()
        return self.get_response(request)
