from django import template

register = template.Library()

@register.filter
def grade_color(value):
    if value >= 90: return 'success'
    elif value >= 80: return 'info'
    elif value >= 70: return 'warning'
    return 'danger'