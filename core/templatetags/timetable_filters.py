from django import template

register = template.Library()

@register.filter
def dict_key(value, arg):
    """
    Get a value from a dictionary using a key.
    Usage: {{ my_dict|dict_key:key_name }}
    """
    if isinstance(value, dict):
        return value.get(arg)
    return None

@register.filter
def get_item(value, arg):
    """
    Alternative: Get item by key from dictionary or list.
    """
    try:
        return value[arg]
    except (KeyError, TypeError, IndexError):
        return None