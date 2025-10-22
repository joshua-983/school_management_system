# In securityEvent_views.py
from django.views.generic import ListView
from django.db.models import Q
from core.models import SecurityEvent

class SecurityEventListView(ListView):
    model = SecurityEvent
    template_name = 'core/security_events.html'
    context_object_name = 'security_events'
    paginate_by = 20
    ordering = ['-timestamp']  # Show latest first

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add filtering if needed
        event_type = self.request.GET.get('event_type')
        severity = self.request.GET.get('severity')
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        if severity:
            queryset = queryset.filter(severity=severity)
            
        return queryset