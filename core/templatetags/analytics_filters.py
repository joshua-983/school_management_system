from django import template

register = template.Library()

@register.filter
def subtract(value, arg):
    """Subtract the arg from the value"""
    return value - arg