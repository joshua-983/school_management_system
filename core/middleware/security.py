# core/middleware/security.py
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from django.shortcuts import render
from django.conf import settings
import time

class FinancialSecurityMiddleware(MiddlewareMixin):
    """Security middleware for financial endpoints"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit_requests = 100  # requests per minute
        self.rate_limit_window = 60  # seconds
        
    def __call__(self, request):
        # Skip rate limiting for GET requests
        if request.method != 'GET':
            # Apply rate limiting
            client_ip = self.get_client_ip(request)
            key = f"rate_limit:{client_ip}"
            
            current = cache.get(key, [])
            current_time = time.time()
            
            # Remove old requests
            current = [t for t in current if current_time - t < self.rate_limit_window]
            
            if len(current) >= self.rate_limit_requests:
                return JsonResponse({
                    'error': 'Rate limit exceeded. Please try again later.'
                }, status=429)
            
            current.append(current_time)
            cache.set(key, current, self.rate_limit_window)
        
        response = self.get_response(request)
        
        # Add security headers for financial endpoints
        if request.path.startswith('/financial/') or request.path.startswith('/bills/') or request.path.startswith('/fees/'):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response['Permissions-Policy'] = 'payment=(self)'
            
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


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
        key = f"rate_limit_general:{client_ip}"
        
        current = cache.get(key, [])
        current_time = time.time()
        
        # Remove old requests
        current = [t for t in current if current_time - t < self.window]
        
        if len(current) >= self.max_requests:
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