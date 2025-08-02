from django import template

register = template.Library()

@register.filter
def unread_notifications_count(user):
    return user.notifications.filter(is_read=False).count()
