from django import template

register = template.Library()

@register.filter
def filter_by_published(queryset, is_published):
    return [item for item in queryset if getattr(item, 'is_published', False) == is_published]

@register.filter
def avg_score(queryset):
    if not queryset:
        return 0
    total = sum(getattr(item, 'average_score', 0) for item in queryset)
    return total / len(queryset)