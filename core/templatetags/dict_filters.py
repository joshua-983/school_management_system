# core/templatetags/dict_filters.py
from django import template

register = template.Library()

@register.filter
def dict_key(d, key):
    """Get a value from a dictionary using a key"""
    try:
        return d.get(key)
    except (AttributeError, KeyError, TypeError):
        return None

@register.filter
def get_item(dictionary, key):
    """Alternative name for dict_key"""
    return dict_key(dictionary, key)