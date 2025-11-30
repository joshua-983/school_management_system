from django import template
from django.conf import settings

register = template.Library()

@register.simple_tag
def is_security_enabled():
    """Check if security features are enabled"""
    return getattr(settings, 'ENABLE_SECURITY_FEATURES', True)

@register.simple_tag
def get_security_level():
    """Get current security level"""
    return getattr(settings, 'SECURITY_LEVEL', 'standard')

@register.filter
def can_view_sensitive(user):
    """Check if user can view sensitive information"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)

@register.simple_tag
def is_maintenance_mode():
    """Check if maintenance mode is active"""
    try:
        from core.models import MaintenanceMode
        maintenance = MaintenanceMode.objects.filter(is_active=True).first()
        return maintenance and maintenance.is_currently_active()
    except:
        return False

@register.simple_tag
def can_bypass_maintenance(user):
    """Check if user can bypass maintenance mode"""
    try:
        from core.models import MaintenanceMode
        maintenance = MaintenanceMode.objects.filter(is_active=True).first()
        return maintenance and maintenance.can_user_bypass(user)
    except:
        return False
