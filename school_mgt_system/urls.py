# school_mgt_system/urls.py - COMPLETE FIXED VERSION WITH HOMEPAGE AND REDIRECTS
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView, TemplateView

# Import the home view from your core app
from core.views.base_views import home

urlpatterns = [
    # ==============================
    # ROOT HOMEPAGE
    # ==============================
    # Add the home view at root URL to prevent 404
    path('', home, name='home'),
    
    # ==============================
    # BACKWARD COMPATIBILITY REDIRECTS
    # ==============================
    # Fix for announcements 404 errors (add these lines)
    path('announcements/active/', 
         RedirectView.as_view(url='/admin/announcements/active/', permanent=True)),
    path('announcements/', 
         RedirectView.as_view(url='/admin/announcements/', permanent=True)),
    
    # ==============================
    # CORE APPLICATION URLS
    # ==============================
    # All core URLs under /admin/ path ONLY
    path('admin/', include('core.urls')),
    
    # ==============================
    # DJANGO ADMIN
    # ==============================
    # Django's built-in admin at separate path to avoid conflicts
    path('django-admin/', admin.site.urls),
    
    # ==============================
    # LOGIN REDIRECTS (Backward Compatibility)
    # ==============================
    # Redirect all old login URLs to the new signin URL in accounts app
    path('login/', RedirectView.as_view(pattern_name='signin', permanent=True)),
    path('accounts/login/', RedirectView.as_view(pattern_name='signin', permanent=True)),
    path('auth/login/', RedirectView.as_view(pattern_name='signin', permanent=True)),
    
    # ==============================
    # ACCOUNTS APP (Authentication)
    # ==============================
    # Your custom accounts URLs (this should contain signin/, signup/, logout/, etc.)
    path('accounts/', include('accounts.urls')),
    
    # ==============================
    # FINANCIAL MODULE
    # ==============================
    # Financial URLs (separate from main core URLs)
    path('financial/', include('core.urls_financial')),
]

# ==============================
# DEBUG TOOLBAR (Development Only)
# ==============================
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
    
    # ==============================
    # STATIC & MEDIA FILES (Development Only)
    # ==============================
    # Serve static files during development
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Serve media files during development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ==============================
# ERROR PAGES (Optional - Custom Error Pages)
# ==============================
if not settings.DEBUG:
    # Make sure these views exist in your base_views.py
    handler404 = 'core.views.base_views.custom_404_view'
    handler500 = 'core.views.base_views.custom_500_view'