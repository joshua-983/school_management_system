# core/middleware/maintenance_middleware.py
import logging
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from core.models import MaintenanceMode

logger = logging.getLogger(__name__)

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check for session bypass first (emergency access)
        if request.session.get('maintenance_bypass'):
            # Allow access if emergency bypass is active
            logger.info(f"Maintenance bypass active for user from IP: {self.get_client_ip(request)}")
            return self.get_response(request)
        
        # Check if maintenance mode is active
        try:
            maintenance = MaintenanceMode.get_current_maintenance()
            
            if maintenance and maintenance.is_currently_active():
                # Check if user can bypass maintenance
                if not MaintenanceMode.can_user_access(request.user):
                    # User cannot bypass - redirect to maintenance page
                    # But allow access to maintenance page itself and static files
                    allowed_paths = [
                        reverse('maintenance_mode_page'),
                        '/static/',
                        '/media/',
                        '/admin/login/',
                        '/accounts/login/',
                        '/security/maintenance-mode/',  # Allow access to maintenance management
                        '/emergency-bypass/',  # Allow access to emergency bypass
                    ]
                    
                    current_path = request.path
                    is_allowed_path = any(current_path.startswith(path) for path in allowed_paths)
                    
                    if not is_allowed_path:
                        logger.info(f"Redirecting user to maintenance page. Path: {current_path}, IP: {self.get_client_ip(request)}")
                        return redirect('maintenance_mode_page')
        except Exception as e:
            logger.error(f"Error in maintenance mode middleware: {e}")
        
        response = self.get_response(request)
        return response

    def get_client_ip(self, request):
        """Get the client's IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip