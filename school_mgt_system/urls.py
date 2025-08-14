
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from school_mgt_system import consumers
from core.views import NotificationListView, mark_notification_read

urlpatterns = [

    path('admin/', admin.site.urls),
    path('core/', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('', TemplateView.as_view(template_name='core/home.html'), name='home'),
    path('notifications/', NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/mark-read/', mark_notification_read, name='mark_notification_read'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    

