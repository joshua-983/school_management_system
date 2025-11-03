# core/middleware.py
from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver
from django.core.cache import cache
from django.contrib.auth import logout
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


@receiver(user_login_failed)
def track_failed_logins(sender, credentials, request, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    cache_key = f'failed_logins_{ip}'
    failures = cache.get(cache_key, 0) + 1
    cache.set(cache_key, failures, timeout=3600)  # 1 hour
    
    if failures >= 5:  # Alert threshold
        from .tasks import send_security_alert
        send_security_alert.delay(
            ip=ip,
            username=credentials.get('username'),
            count=failures
        )

class PasswordRotationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (request.user.is_authenticated and 
                hasattr(request.user, 'last_password_change') and
                (timezone.now() - request.user.last_password_change).days > settings.PASSWORD_ROTATION_DAYS):
            logout(request)
            return redirect(f"{reverse('password_change')}?expired=1")
        return self.get_response(request)

# ADD THIS CLASS TO FIX THE ERROR:
class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Custom security headers middleware for enhanced security
    """
    def process_response(self, request, response):
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Remove server header
        if 'Server' in response:
            del response['Server']
            
        return response