"""
ASGI config for school_mgt_system project.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgt_system.settings')

# Initialize Django first
django_application = get_asgi_application()

# Then try to set up WebSockets
try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from django.urls import path
    
    # Import consumers after Django is initialized
    from .consumers import NotificationConsumer
    
    application = ProtocolTypeRouter({
        "http": django_application,
        "websocket": AuthMiddlewareStack(
            URLRouter([
                path("ws/notifications/", NotificationConsumer.as_asgi()),
            ])
        ),
    })
except ImportError as e:
    print(f"Channels not available, using basic ASGI: {e}")
    application = django_application
except Exception as e:
    print(f"WebSocket setup failed, using basic ASGI: {e}")
    application = django_application