# core/mixins.py
from django.contrib.auth.mixins import AccessMixin
from django_otp import user_has_device

class OTPRequiredMixin(AccessMixin):
    """Verify that the user is authenticated and has verified OTP."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_has_device(request.user):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)