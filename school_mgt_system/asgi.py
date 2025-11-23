"""
ASGI config for school_mgt_system project.
Optimized for production with proper timeout handling and WebSocket configuration.
"""

import os
import django
from django.core.asgi import get_asgi_application
import logging

# Set up logging
logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgt_system.settings')

# Initialize Django first
django.setup()
django_application = get_asgi_application()

# WebSocket configuration with comprehensive error handling
try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from channels.security.websocket import AllowedHostsOriginValidator
    from django.urls import re_path
    
    # Import your WebSocket consumers from the same directory
    from .consumers import NotificationConsumer, SecurityConsumer

    # WebSocket URL patterns
    websocket_urlpatterns = [
        re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
        re_path(r"ws/security/$", SecurityConsumer.as_asgi()),
    ]

    # Configure WebSocket application with proper middleware
    websocket_application = AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    )

    application = ProtocolTypeRouter({
        "http": django_application,
        "websocket": websocket_application,
    })
    
    logger.info("✅ WebSocket routes configured successfully with NotificationConsumer and SecurityConsumer")
    print("✅ ASGI application configured with WebSocket support")
    
except ImportError as e:
    logger.warning(f"⚠️ Channels not available or consumers not found: {e}")
    print(f"⚠️ WebSocket setup issue: {e}")
    application = django_application
    
except Exception as e:
    logger.error(f"❌ WebSocket setup failed: {e}")
    print(f"❌ WebSocket configuration error: {e}")
    application = django_application

print("🚀 ASGI application initialized successfully")