# core/middleware.py
from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver
from django.core.cache import cache
from django.contrib.auth import logout
from django.urls import reverse
from django.utils import timezone


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


