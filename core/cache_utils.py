from django.core.cache import cache
from django.db.models import Model
from typing import Union, Optional

def get_cached_or_query(
    cache_key: str,
    queryset,
    timeout: int = 3600,
    version: Optional[str] = None
) -> Union[Model, list]:
    """
    Generic cache retrieval with fallback to queryset execution
    """
    data = cache.get(cache_key, version=version)
    if data is not None:
        return data
    
    data = list(queryset) if hasattr(queryset, '__iter__') else queryset
    cache.set(cache_key, data, timeout, version=version)
    return data

def invalidate_cache(cache_key: str, version: Optional[str] = None) -> None:
    """Invalidate specific cache key"""
    cache.delete(cache_key, version=version)

# Example usage in view:
# students = get_cached_or_query('all_students', Student.objects.all())