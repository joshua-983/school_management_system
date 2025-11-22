# core/mixins.py
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin, AccessMixin
from django_otp import user_has_device
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Helper functions for role checking
def is_admin(user):
    """Check if user is an admin"""
    return hasattr(user, 'admin') or user.is_superuser or user.is_staff

def is_teacher(user):
    """Check if user is a teacher"""
    return hasattr(user, 'teacher')

def is_student(user):
    """Check if user is a student"""
    return hasattr(user, 'student')

def is_parent(user):
    """Check if user is a parent"""
    return hasattr(user, 'parentguardian')


class TwoFactorLoginRequiredMixin(LoginRequiredMixin):
    """LoginRequiredMixin that uses your signin URL"""
    login_url = reverse_lazy('signin')  # Use your actual signin URL
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
    
    def get_login_url(self):
        return self.login_url


class AdminRequiredMixin(UserPassesTestMixin):
    """Require admin or superuser access"""
    
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or is_admin(user))
    
    def handle_no_permission(self):
        messages.error(self.request, "Administrator access required.")
        return redirect('dashboard')


class TeacherRequiredMixin(UserPassesTestMixin):
    """Require teacher access"""
    
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and is_teacher(user)
    
    def handle_no_permission(self):
        messages.error(self.request, "Teacher access required.")
        return redirect('dashboard')


class StudentRequiredMixin(UserPassesTestMixin):
    """Require student access"""
    
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and is_student(user)
    
    def handle_no_permission(self):
        messages.error(self.request, "Student access required.")
        return redirect('dashboard')


class ParentRequiredMixin(UserPassesTestMixin):
    """Require parent access"""
    
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and is_parent(user)
    
    def handle_no_permission(self):
        messages.error(self.request, "Parent access required.")
        return redirect('dashboard')


class TeacherOwnershipMixin(UserPassesTestMixin):
    """Mixin to verify that the current user (teacher) owns the object."""
    
    def test_func(self):
        if not hasattr(self.request.user, 'teacher'):
            return False
        
        obj = self.get_object()
        
        # Check various ownership scenarios
        if hasattr(obj, 'teacher') and obj.teacher == self.request.user.teacher:
            return True
        
        elif hasattr(obj, 'class_assignment') and obj.class_assignment.teacher == self.request.user.teacher:
            return True
        
        elif hasattr(obj, 'recorded_by') and obj.recorded_by == self.request.user:
            return True
        
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to access this resource.")
        return redirect('dashboard')


class AuditLogMixin:
    """Mixin to automatically create audit logs for model operations"""
    
    def form_valid(self, form):
        response = super().form_valid(form)
        self._create_audit_log('CREATE' if self.object._state.adding else 'UPDATE')
        return response
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self._create_audit_log('DELETE')
        return super().delete(request, *args, **kwargs)
    
    def _create_audit_log(self, action):
        """Create audit log entry"""
        try:
            from .models import AuditLog
            
            AuditLog.objects.create(
                user=self.request.user,
                action=action,
                model_name=self.object._meta.model_name,
                object_id=self.object.pk,
                details=self._get_audit_details(action),
                ip_address=self._get_client_ip()
            )
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
    
    def _get_audit_details(self, action):
        """Get details for audit log"""
        details = {
            'action': action,
            'timestamp': timezone.now().isoformat(),
            'model': self.object._meta.model_name,
        }
        
        if action == 'UPDATE' and hasattr(self, '_changes'):
            details['changes'] = self._changes
        
        return details
    
    def _get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class CacheControlMixin:
    """Mixin for controlling cache headers"""
    
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        
        # Add cache control headers
        if hasattr(self, 'cache_timeout'):
            response['Cache-Control'] = f'max-age={self.cache_timeout}'
        else:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response


class FormMessagesMixin:
    """Mixin for consistent form success/error messages"""
    
    success_message = None
    error_message = "There was an error processing your request. Please try again."
    
    def form_valid(self, form):
        response = super().form_valid(form)
        if self.success_message:
            messages.success(self.request, self.success_message)
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, self.error_message)
        return super().form_invalid(form)