from django import template

register = template.Library()

@register.filter
def subtract(value, arg):
    return value - arg

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def is_admin(user):
    """Check if user is in Admin group or is superuser"""
    return user.groups.filter(name='Admin').exists() or user.is_superuser

# ADD THIS NEW FILTER:
@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def in_list(value, arg):
    """Check if value is in the comma-separated list"""
    return value in arg.split(',')