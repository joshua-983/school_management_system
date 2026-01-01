# core/middleware/async_otp_middleware.py
"""
Async-compatible wrapper for Django OTP middleware.
"""
from asgiref.sync import sync_to_async
from django_otp.middleware import OTPMiddleware as BaseOTPMiddleware
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

class AsyncOTPMiddleware(MiddlewareMixin):
    """
    Async-compatible OTP middleware wrapper.
    """
    sync_capable = True
    async_capable = True
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.base_otp_middleware = BaseOTPMiddleware(get_response)
    
    async def __call__(self, request):
        """Async call handler"""
        # Use sync_to_async for OTP verification
        try:
            await sync_to_async(self.base_otp_middleware.process_request)(request)
            response = await self.get_response(request)
            await sync_to_async(self.base_otp_middleware.process_response)(request, response)
            return response
        except Exception as e:
            logger.error(f"OTP middleware error: {str(e)}")
            response = await self.get_response(request)
            return response