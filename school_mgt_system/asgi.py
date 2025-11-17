# school_mgt_system/asgi.py
"""
ASGI config for school_mgt_system project.
"""

import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgt_system.settings')

# Initialize Django first
django.setup()
django_application = get_asgi_application()

# Then set up WebSockets
try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from channels.security.websocket import AllowedHostsOriginValidator
    from django.urls import re_path
    
    # Import consumers after Django is initialized
    from .consumers import NotificationConsumer, SecurityConsumer

    # WebSocket URL patterns
    websocket_urlpatterns = [
        re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
        re_path(r"ws/security/$", SecurityConsumer.as_asgi()),
    ]

    application = ProtocolTypeRouter({
        "http": django_application,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    })
    
    print("✅ WebSocket routes configured:")
    print("   - /ws/notifications/")
    print("   - /ws/security/")
    
except ImportError as e:
    print(f"❌ Channels not available, using basic ASGI: {e}")
    application = django_application
except Exception as e:
    print(f"❌ WebSocket setup failed, using basic ASGI: {e}")
    application = django_application
