"""
Content Security Policy Middleware
Updated to allow common CDN resources for development
"""
class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # More permissive CSP for development
        # Allows common CDNs used by Bootstrap, Font Awesome, jQuery, etc.
        csp_policy = [
            "default-src 'self'",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com",
            "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "img-src 'self' data: https:",
            "connect-src 'self'",
            "frame-ancestors 'self'",
            "form-action 'self'",
            "base-uri 'self'",
        ]
        
        response['Content-Security-Policy'] = "; ".join(csp_policy)
        return response
