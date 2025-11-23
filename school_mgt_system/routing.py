# management_system/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/notifications/$", consumers.NotificationConsumer.as_asgi()),
    re_path(r"ws/security/$", consumers.SecurityConsumer.as_asgi()),
]

# Application routing
application = {
    'http': None,  # We're not using HTTP protocol for WebSockets
    'websocket': consumers.NotificationConsumer.as_asgi(),
}