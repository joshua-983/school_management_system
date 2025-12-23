"""
General data manipulation helpers.
"""
import json
from datetime import datetime, date
from decimal import Decimal
from django.db.models import Q, Avg, Sum, Count

def dict_to_json(data):
    """Convert dict to JSON string with proper serialization"""
    def json_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Type {type(obj)} not serializable")
    
    return json.dumps(data, default=json_serializer, indent=2)

def filter_queryset(queryset, filters):
    """Apply multiple filters to a queryset"""
    if not filters:
        return queryset
    
    q_objects = Q()
    
    for field, value in filters.items():
        if value is not None and value != '':
            if field.endswith('__icontains'):
                q_objects &= Q(**{field: value})
            else:
                q_objects &= Q(**{field: value})
    
    return queryset.filter(q_objects)

def aggregate_queryset(queryset, aggregations):
    """Apply aggregations to a queryset"""
    if not aggregations:
        return {}
    
    return queryset.aggregate(**aggregations)

def group_queryset(queryset, group_by, aggregations=None):
    """Group queryset by field and optionally apply aggregations"""
    if aggregations:
        return queryset.values(group_by).annotate(**aggregations).order_by(group_by)
    else:
        return queryset.values(group_by).distinct().order_by(group_by)

__all__ = [
    'dict_to_json',
    'filter_queryset',
    'aggregate_queryset',
    'group_queryset',
]