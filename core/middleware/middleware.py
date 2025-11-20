from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver
from django.core.cache import cache
from django.contrib.auth import logout
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.shortcuts import render
from django.contrib.auth.models import AnonymousUser
import time


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
    Enhanced security headers middleware
    """
    def process_response(self, request, response):
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Content Security Policy
        if settings.ENABLE_CSP:
            csp_policy = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
                "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
                "img-src 'self' data: https:",
                "connect-src 'self'",
                "frame-ancestors 'none'",
                "base-uri 'self'",
                "form-action 'self'"
            ]
            response['Content-Security-Policy'] = '; '.join(csp_policy)
        
        # Remove server header
        if 'Server' in response:
            del response['Server']
            
        return response


class MaintenanceModeMiddleware(MiddlewareMixin):
    """
    Maintenance mode middleware
    """
    def process_request(self, request):
        # Skip maintenance mode for staff users and specific paths
        if (hasattr(request, 'user') and 
            (request.user.is_staff or 
             request.path.startswith('/admin/') or
             request.path.startswith('/security/') or
             request.path == '/maintenance/')):
            return None
        
        if getattr(settings, 'MAINTENANCE_MODE', False):
            return render(request, 'security/maintenance.html', status=503)
        
        return None


class UserBlockMiddleware(MiddlewareMixin):
    """
    Check if user is blocked
    """
    def process_request(self, request):
        if (hasattr(request, 'user') and 
            not isinstance(request.user, AnonymousUser) and 
            hasattr(request.user, 'profile') and 
            request.user.profile.is_blocked):
            
            # Allow logout even when blocked
            if request.path == '/logout/':
                return None
                
            return render(request, 'security/user_blocked.html', status=403)
        
        return None

class RateLimitMiddleware(MiddlewareMixin):
    """
    Basic rate limiting middleware
    """
    def __call__(self, request):
        response = self.process_request(request)
        if response:
            return response
        return self.get_response(request)

    def process_request(self, request):
        if not hasattr(request, 'user') or isinstance(request.user, AnonymousUser):
            return None
            
        # Simple IP-based rate limiting
        ip = self.get_client_ip(request)
        cache_key = f'rate_limit_{ip}'
        
        # Rate limiting using cache
        requests = cache.get(cache_key, [])
        
        # Clean old requests (last minute)
        current_time = time.time()
        requests = [req_time for req_time in requests if current_time - req_time < 60]
        
        # Check if over limit
        if len(requests) >= getattr(settings, 'RATE_LIMIT_REQUESTS', 100):
            return render(request, 'security/rate_limit_exceeded.html', status=429)
        
        # Add current request
        requests.append(current_time)
        cache.set(cache_key, requests, 60)
        
        return None
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip



















class UserBlockMiddleware:
    """Middleware to handle blocked users"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Check if user is blocked
        if (request.user.is_authenticated and 
            hasattr(request.user, 'profile') and 
            getattr(request.user.profile, 'is_blocked', False)):
            
            from django.shortcuts import redirect
            from django.urls import reverse
            
            # Allow access to blocked page and logout
            if (request.path not in [reverse('user_blocked'), reverse('signout')] and
                not request.path.startswith('/admin/')):
                return redirect('user_blocked')
        
        return self.get_response(request)


class MaintenanceModeMiddleware:
    """Middleware to handle maintenance mode"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        from django.conf import settings
        from django.shortcuts import render
        
        # Check if maintenance mode is enabled
        if getattr(settings, 'MAINTENANCE_MODE', False):
            # Allow access to maintenance page and admin
            if (request.path != '/maintenance/' and
                not request.path.startswith('/admin/') and
                not request.path.startswith('/static/') and
                not request.path.startswith('/media/')):
                return render(request, 'security/maintenance.html', status=503)
        
        return self.get_response(request)
