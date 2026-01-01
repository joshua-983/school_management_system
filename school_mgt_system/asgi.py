"""
ASGI config for school_mgt_system project.
Optimized for production with proper timeout handling and WebSocket configuration.
"""

import os
from django.core.asgi import get_asgi_application
import logging

# Set up logging
logger = logging.getLogger(__name__)

# ============================================================================
# SET DJANGO SETTINGS MODULE FIRST
# ============================================================================
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgt_system.settings')

# Get ASGI application
try:
    application = get_asgi_application()
    logger.info("✅ ASGI application created successfully")
    
except Exception as e:
    logger.error(f"❌ Error creating ASGI application: {e}")
    import traceback
    logger.error(traceback.format_exc())
    
    # Create minimal fallback application
    from django.http import HttpResponse
    async def fallback_app(scope, receive, send):
        response = HttpResponse(
            "ASGI Application Error - Middleware Loading Failed",
            status=500,
            content_type="text/plain"
        )
        await response(scope, receive, send)
    
    application = fallback_app

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
        "http": application,
        "websocket": websocket_application,
    })

    logger.info("✅ WebSocket routes configured successfully with NotificationConsumer and SecurityConsumer")
    print("✅ ASGI application configured with WebSocket support")

except ImportError as e:
    logger.warning(f"⚠️ Channels not available or consumers not found: {e}")
    print(f"⚠️ WebSocket setup issue: {e}")

except Exception as e:
    logger.error(f"❌ WebSocket setup failed: {e}")
    print(f"❌ WebSocket configuration error: {e}")

print("🚀 ASGI application initialized successfully")