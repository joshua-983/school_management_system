from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # ONLY your custom accounts URLs (remove the django.contrib.auth.urls line)
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