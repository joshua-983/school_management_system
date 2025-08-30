# core/filters.py
import django_filters
from .models import AuditLog
from django.contrib.auth.mixins import LoginRequiredMixin  # Add this import
from django.views.generic import ListView  # Add this import

class AuditLogFilter(django_filters.FilterSet):
    date_range = django_filters.DateFromToRangeFilter(field_name='timestamp')
    action = django_filters.CharFilter(lookup_expr='icontains')
    model = django_filters.CharFilter(field_name='model_name', lookup_expr='icontains')
    
    class Meta:
        model = AuditLog
        fields = ['user', 'action', 'ip_address']
