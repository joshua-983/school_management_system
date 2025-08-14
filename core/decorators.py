# core/decorators.py
from django.core.cache import cache

def cache_fee_balance(view_func):
    @wraps(view_func)
    def _wrapped_view(request, student_id, *args, **kwargs):
        cache_key = f'fee_balance_{student_id}'
        balance = cache.get(cache_key)
        
        if balance is None:
            response = view_func(request, student_id, *args, **kwargs)
            if response.status_code == 200:
                cache.set(cache_key, response.content, timeout=60*60)  # 1 hour
            return response
        return HttpResponse(balance)
    return _wrapped_view