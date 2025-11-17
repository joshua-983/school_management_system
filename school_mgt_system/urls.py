# main/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView  # ADD THIS IMPORT

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Redirect old login URLs to new signin URL - ADD THESE LINES
    path('login/', RedirectView.as_view(pattern_name='signin', permanent=True)),
    path('accounts/login/', RedirectView.as_view(pattern_name='signin', permanent=True)),
    
    # Your custom accounts URLs
    path('accounts/', include('accounts.urls')), 
    
    # Core app URLs
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