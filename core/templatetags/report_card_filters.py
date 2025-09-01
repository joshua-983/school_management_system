from django import template

register = template.Library()

@register.filter
def filter_by_published(queryset, is_published):
    return [item for item in queryset if item.is_published == is_published]

@register.filter
def avg_score(queryset):
    if not queryset:
        return 0
    total = sum(item.average_score for item in queryset if hasattr(item, 'average_score'))
    return total / len(queryset)