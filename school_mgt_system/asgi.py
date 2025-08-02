import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from . import consumers  # Import your consumers

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgt_system.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path("ws/notifications/", consumers.NotificationConsumer.as_asgi()),
        ])
    ),
})