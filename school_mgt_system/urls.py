# school_mgt_system/urls.py - UPDATED VERSION
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    # CUSTOM ADMIN PATTERNS FIRST - This will catch /admin/timetable/* before Django Admin
    # Note: All custom admin URLs in core/urls.py should use 'admin/' prefix
    path('admin/', include('core.urls')),  # This line MUST come before admin.site.urls
    
    # Django's built-in admin (now at /django-admin/ to avoid conflicts)
    path('django-admin/', admin.site.urls),
    
    # Redirect all old login URLs to the new signin URL
    path('login/', RedirectView.as_view(pattern_name='signin', permanent=True)),
    path('accounts/login/', RedirectView.as_view(pattern_name='signin', permanent=True)),
    path('auth/login/', RedirectView.as_view(pattern_name='signin', permanent=True)),
    
    # Your custom accounts URLs (this should contain signin/)
    path('accounts/', include('accounts.urls')), 
    
    # Core app URLs for non-admin paths (these should NOT start with 'admin/')
    # This will handle paths like /students/, /teachers/, /timetable/, etc.
    path('', include('core.urls')),
]

# Add debug toolbar URLs only in development
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
    
    # Static and media files for development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)