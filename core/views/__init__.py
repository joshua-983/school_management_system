"""
Views package initialization with CSRF handling.
"""
from django.shortcuts import render
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.decorators import decorator_from_middleware

# FIX THIS LINE - Import from core.models, not core.views
from core.models import Budget, Expense

def csrf_failure(request, reason=""):
    """
    Custom CSRF failure view with better user experience
    """
    context = {
        'title': 'Security Verification Failed',
        'message': 'We could not verify your security token. This may happen if:',
        'reasons': [
            'Your session expired',
            'You have cookies disabled',
            'The page was open for too long',
            'You submitted the form from a different browser/tab'
        ],
        'solutions': [
            'Refresh the page and try again',
            'Enable cookies in your browser',
            'Make sure you are using the same browser and tab',
            'If the problem persists, clear your browser cache and cookies'
        ]
    }
    return render(request, 'core/errors/csrf_failure.html', context, status=403)