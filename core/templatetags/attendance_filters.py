from django import template

register = template.Library()

@register.filter(name='attendance_count')
def attendance_count(attendances, status):
    return attendances.filter(status=status).count()


@register.filter(name='divide')
def divide(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter(name='multiply')
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except ValueError:
        return 0