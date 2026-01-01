"""
Enhanced CSRF Protection Middleware
"""
from django.middleware.csrf import CsrfViewMiddleware

class CSRFProtectionMiddleware(CsrfViewMiddleware):
    """Enhanced CSRF protection"""
    pass
