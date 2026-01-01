"""
Password Rotation Middleware
"""
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

class PasswordRotationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Check if password needs rotation
            password_rotation_days = getattr(settings, 'PASSWORD_ROTATION_DAYS', 90)
            # You would check the user's last password change here
            # and redirect to password change page if needed
            pass
        return self.get_response(request)
