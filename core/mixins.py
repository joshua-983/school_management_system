# core/mixins.py
from django.contrib.auth.mixins import AccessMixin
from django_otp import user_has_device
from django.core.exceptions import PermissionDenied
class OTPRequiredMixin(AccessMixin):
    """Verify that the user is authenticated and has verified OTP."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_has_device(request.user):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)



class TeacherOwnershipRequiredMixin:
    """Mixin to verify that the current user (teacher) owns the object."""
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        # Check if the object has a 'teacher' field and if it matches the request user's teacher profile
        if hasattr(obj, 'teacher') and obj.teacher != request.user.teacher:
            raise PermissionDenied("You do not have permission to edit this assignment.")
        # Check if the object is related to a ClassAssignment owned by the teacher
        elif hasattr(obj, 'class_assignment') and obj.class_assignment.teacher != request.user.teacher:
            raise PermissionDenied("You do not have permission to edit this assignment.")
        return super().dispatch(request, *args, **kwargs)