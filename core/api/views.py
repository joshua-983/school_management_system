# core/api/views.py
from core.utils.error_handling import handle_api_exception
from core.exceptions import PermissionDeniedError

@handle_api_exception
def grade_api_view(request):
    if not request.user.has_perm('core.change_grade'):
        raise PermissionDeniedError("API access denied")
    
    # Your API logic
    return JsonResponse({'status': 'success'})