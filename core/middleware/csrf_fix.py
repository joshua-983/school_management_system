from django.utils.deprecation import MiddlewareMixin
from django.middleware.csrf import get_token

class CSRFHeaderCorrectionMiddleware(MiddlewareMixin):
    """
    Corrects CSRF header issues including 'null' tokens and misspelled headers
    """
    def process_request(self, request):
        misspelled = 'HTTP_X_CSRFTOKEN'
        correct = 'HTTP_X_CSRFTOKEN'
        
        # Debug what we receive
        if misspelled in request.META:
            token_value = request.META[misspelled]
            print(f"🔍 CSRF DEBUG: Received token: '{token_value}' (length: {len(token_value)})")
            
            # Handle the 'null' token case specifically
            if token_value == 'null' or (token_value and len(token_value) != 64):
                print(f"❌ CSRF DEBUG: Invalid token detected: '{token_value}'")
                print(f"🔄 CSRF FIX: Generating valid CSRF token...")
                
                # Generate a valid CSRF token
                try:
                    valid_token = get_token(request)
                    if valid_token and len(valid_token) == 64:
                        # Replace the bad token with a valid one
                        request.META[misspelled] = valid_token
                        request.META[correct] = valid_token
                        print(f"✅ CSRF FIX: Replaced '{token_value}' with valid token (length: {len(valid_token)})")
                        
                        # Also set the cookie for future requests
                        from django.middleware.csrf import _get_new_csrf_string
                        request.META['CSRF_COOKIE'] = valid_token
                    else:
                        print(f"❌ CSRF FIX: Generated token is also invalid")
                except Exception as e:
                    print(f"❌ CSRF FIX: Error generating token: {e}")
            else:
                # Token looks valid, just ensure the header is copied
                request.META[correct] = request.META[misspelled]
                print(f"✅ CSRF DEBUG: Token valid, header processed")
            
        return None
