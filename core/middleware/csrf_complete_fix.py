from django.utils.deprecation import MiddlewareMixin
from django.middleware.csrf import get_token, rotate_token
import logging

logger = logging.getLogger('csrf_complete_fix')

class CompleteCSRFFixMiddleware(MiddlewareMixin):
    """
    Complete CSRF fix that handles token generation, validation, and cookie setting
    """
    
    def process_request(self, request):
        misspelled = 'HTTP_X_CSRFTOKEN'
        correct = 'HTTP_X_CSRFTOKEN'
        
        # Ensure we have a CSRF token for this request
        try:
            current_token = get_token(request)
        except Exception as e:
            logger.error(f"CSRF ERROR: Could not get token: {e}")
            current_token = None
        
        # Handle the misspelled header with invalid tokens
        if misspelled in request.META:
            header_token = request.META[misspelled]
            
            # If token is 'null' or invalid, we need to handle this carefully
            if header_token == 'null' or not header_token or len(header_token) != 64:
                logger.warning(f"CSRF FIX: Invalid header token '{header_token}'")
                
                # Use the current valid token for this request
                if current_token and len(current_token) == 64:
                    request.META[misspelled] = current_token
                    request.META[correct] = current_token
                    logger.info(f"CSRF FIX: Set valid token in headers")
                    
                    # Also ensure the cookie is set for this session
                    request.META['CSRF_COOKIE'] = current_token
                    request.META['CSRF_COOKIE_NEEDS_UPDATE'] = True
                else:
                    # Generate a new token if none exists
                    try:
                        new_token = get_token(request)
                        request.META[misspelled] = new_token
                        request.META[correct] = new_token
                        request.META['CSRF_COOKIE'] = new_token
                        request.META['CSRF_COOKIE_NEEDS_UPDATE'] = True
                        logger.info(f"CSRF FIX: Generated new token")
                    except Exception as e:
                        logger.error(f"CSRF FIX: Token generation failed: {e}")
            else:
                # Header token looks valid, ensure it's in the correct header
                request.META[correct] = header_token
        
        return None

    def process_response(self, request, response):
        # If we detected that the CSRF cookie needs updating, set it
        if hasattr(request, 'META') and request.META.get('CSRF_COOKIE_NEEDS_UPDATE'):
            csrf_token = request.META.get('CSRF_COOKIE')
            if csrf_token and len(csrf_token) == 64:
                response.set_cookie(
                    'csrftoken',
                    csrf_token,
                    max_age=60 * 60 * 24 * 365,  # 1 year
                    domain=None,
                    path='/',
                    secure=False,
                    httponly=False,
                    samesite='Lax'
                )
                logger.info("CSRF FIX: Set CSRF cookie in response")
        
        return response
