# core/middleware/middleware.py
from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver
from django.core.cache import cache
from django.contrib.auth import logout
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.shortcuts import redirect, render
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
import time


@receiver(user_login_failed)
def track_failed_logins(sender, credentials, request, **kwargs):
    """Track failed login attempts"""
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


class PasswordRotationMiddleware(MiddlewareMixin):
    """Middleware to enforce password rotation"""
    
    def __call__(self, request):
        if (request.user.is_authenticated and 
                hasattr(request.user, 'last_password_change') and
                (timezone.now() - request.user.last_password_change).days > getattr(settings, 'PASSWORD_ROTATION_DAYS', 90)):
            logout(request)
            return redirect(f"{reverse('password_change')}?expired=1")
        
        response = self.get_response(request)
        return response


# Since your __init__.py expects these classes in middleware.py, let me add them
class SecurityHeadersMiddleware(MiddlewareMixin):
    """Enhanced security headers middleware"""
    
    def process_response(self, request, response):
        # Only modify HttpResponse objects, not coroutines or other types
        if not isinstance(response, HttpResponse):
            return response
            
        # Basic security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Add HSTS if using HTTPS
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """Basic rate limiting middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.max_requests = 100  # requests per minute
        self.window = 60  # seconds
        
    def __call__(self, request):
        # Skip rate limiting for certain paths
        excluded_paths = ['/static/', '/media/', '/favicon.ico']
        if any(request.path.startswith(path) for path in excluded_paths):
            return self.get_response(request)
            
        # Apply rate limiting
        client_ip = self.get_client_ip(request)
        key = f"rate_limit:{client_ip}"
        
        current = cache.get(key, [])
        current_time = time.time()
        
        # Remove old requests
        current = [t for t in current if current_time - t < self.window]
        
        if len(current) >= self.max_requests:
            from django.http import JsonResponse
            return JsonResponse({
                'error': 'Rate limit exceeded. Please try again later.'
            }, status=429)
        
        current.append(current_time)
        cache.set(key, current, self.window)
        
        response = self.get_response(request)
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class UserBlockMiddleware(MiddlewareMixin):
    """Check if user is blocked"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if (hasattr(request, 'user') and 
            request.user.is_authenticated and 
            hasattr(request.user, 'profile') and 
            getattr(request.user.profile, 'is_blocked', False)):
            
            # Allow access to blocked page and logout
            allowed_paths = [
                '/logout/', '/signout/', '/security/blocked/',
                '/admin/logout/', '/accounts/logout/'
            ]
            
            if not any(request.path.startswith(path) for path in allowed_paths):
                return render(request, 'security/user_blocked.html', status=403)
        
        response = self.get_response(request)
        return response


class MaintenanceModeMiddleware(MiddlewareMixin):
    """Maintenance mode middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        from django.conf import settings
        
        # Skip maintenance mode for staff and specific paths
        skip_paths = [
            '/admin/', '/login/', '/logout/', '/signout/',
            '/static/', '/media/', '/favicon.ico'
        ]
        
        maintenance_enabled = getattr(settings, 'MAINTENANCE_MODE', False)
        
        if maintenance_enabled:
            # Allow access to allowed users and paths
            user_has_access = (
                hasattr(request, 'user') and 
                request.user.is_authenticated and 
                (request.user.is_staff or request.user.is_superuser)
            )
            
            path_allowed = any(request.path.startswith(path) for path in skip_paths)
            
            if not user_has_access and not path_allowed:
                return render(request, 'security/maintenance.html', status=503)
        
        response = self.get_response(request)
        return response


# Other middleware classes that you might need
class NotificationMiddleware(MiddlewareMixin):
    """Add notification data to template context"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_template_response(self, request, response):
        """Add unread notification count to template context"""
        if hasattr(response, 'context_data') and request.user.is_authenticated:
            try:
                from core.models import Notification
                unread_count = Notification.get_unread_count_for_user(request.user)
                response.context_data['unread_notifications_count'] = unread_count
            except Exception as e:
                response.context_data['unread_notifications_count'] = 0
        
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """Log all requests for debugging and auditing"""
    
    def __call__(self, request):
        # Log request details (can be modified to use proper logging)
        request.start_time = time.time()
        
        response = self.get_response(request)
        
        # Calculate response time
        response_time = time.time() - request.start_time
        
        # Log slow requests
        if response_time > 5.0:  # 5 seconds threshold
            print(f"SLOW REQUEST: {request.method} {request.path} - {response_time:.2f}s")
        
        return response


# Keep the legacy compatibility class to fix async issues
class LegacyMiddlewareCompatibility(MiddlewareMixin):
    """Ensure compatibility with legacy async middleware calls"""
    
    def __call__(self, request):
        try:
            response = self.get_response(request)
            
            # Ensure response is not a coroutine
            if hasattr(response, '__await__'):
                from asgiref.sync import async_to_sync
                try:
                    response = async_to_sync(lambda: response)()
                except Exception as e:
                    print(f"Error converting async response: {str(e)}")
                    return HttpResponse("Internal Server Error", status=500)
                    
            return response
        except Exception as e:
            print(f"Middleware error: {str(e)}")
            return HttpResponse("Internal Server Error", status=500)


# In core/middleware/middleware.py - Add this class

class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """Content Security Policy middleware"""
    
    def process_response(self, request, response):
        # Only modify HttpResponse objects
        from django.http import HttpResponse
        if not isinstance(response, HttpResponse):
            return response
            
        # Only add CSP to HTML responses
        if hasattr(response, 'content_type') and 'text/html' in response.content_type:
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://code.jquery.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
            response['Content-Security-Policy'] = csp
            
        return response


# In core/middleware/middleware.py - Add these missing classes

class CSRFProtectionMiddleware(MiddlewareMixin):
    """Enhanced CSRF protection for sensitive endpoints"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.sensitive_paths = [
            '/fees/', '/bills/', '/financial/', '/payments/',
            '/api/financial/', '/api/payments/'
        ]
        
    def __call__(self, request):
        # Check if it's a sensitive POST request
        if request.method == 'POST':
            is_sensitive = any(request.path.startswith(path) for path in self.sensitive_paths)
            
            if is_sensitive:
                # Verify CSRF token
                csrf_token = request.POST.get('csrfmiddlewaretoken') or request.headers.get('X-CSRFToken')
                
                if not csrf_token or csrf_token != request.META.get('CSRF_COOKIE'):
                    from django.http import JsonResponse
                    return JsonResponse({
                        'error': 'CSRF verification failed. Please refresh the page and try again.'
                    }, status=403)
        
        response = self.get_response(request)
        return response


class SessionTimeoutMiddleware(MiddlewareMixin):
    """Handle session timeout and auto-logout"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if request.user.is_authenticated:
            # Check session age
            session_age = time.time() - request.session.get('_session_init_timestamp_', 0)
            session_timeout = getattr(settings, 'SESSION_COOKIE_AGE', 1209600)
            
            if session_age > session_timeout:
                # Session expired, logout user
                logout(request)
                if request.path not in ['/login/', '/accounts/login/']:
                    return redirect(f"{reverse('login')}?session_expired=1")
        
        response = self.get_response(request)
        
        # Update session timestamp on successful requests
        if request.user.is_authenticated and response.status_code < 400:
            request.session['_session_init_timestamp_'] = time.time()
            
        return response


class ErrorHandlingMiddleware(MiddlewareMixin):
    """Global error handling middleware"""
    
    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            import traceback
            print(f"Unhandled error: {str(e)}")
            print(traceback.format_exc())
            
            # Log the error
            from django.core.mail import mail_admins
            mail_admins(
                'Unhandled Exception',
                f'Path: {request.path}\nError: {str(e)}\nTraceback:\n{traceback.format_exc()}',
                fail_silently=True
            )
            
            # Return user-friendly error page
            if request.path.startswith('/api/'):
                from django.http import JsonResponse
                return JsonResponse({
                    'error': 'Internal server error. Please try again later.'
                }, status=500)
            else:
                return render(request, 'errors/500.html', status=500)