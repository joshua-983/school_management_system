"""
Maintenance Mode Middleware
"""
from django.conf import settings
from django.http import HttpResponse

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        maintenance_mode = getattr(settings, 'MAINTENANCE_MODE', False)
        maintenance_message = getattr(settings, 'MAINTENANCE_MESSAGE', 
                                     "The system is currently under maintenance. Please check back later.")
        
        # Allow admin access even in maintenance mode
        if maintenance_mode and not (request.user.is_staff or request.user.is_superuser):
            # Allow API endpoints if needed
            if request.path.startswith('/api/'):
                return self.get_response(request)
            return HttpResponse(maintenance_message, status=503, content_type='text/html')
        
        return self.get_response(request)
