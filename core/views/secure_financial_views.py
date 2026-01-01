# core/views/secure_financial_views.py
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db import transaction

from core.security.two_factor import Financial2FAService
from core.models.audit import FinancialAuditTrail


@method_decorator(csrf_protect, name='dispatch')
class SecureFinancialView(LoginRequiredMixin, View):
    """Base class for secure financial views with 2FA"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if 2FA is required for this action
        if self._requires_2fa(request):
            if not self._verify_2fa(request):
                return JsonResponse({
                    'success': False,
                    'requires_2fa': True,
                    'message': 'Two-factor authentication required'
                }, status=403)
        
        return super().dispatch(request, *args, **kwargs)
    
    def _requires_2fa(self, request):
        """Check if 2FA is required for this request"""
        # Check amount if provided
        if request.method == 'POST':
            try:
                import json
                data = json.loads(request.body)
                amount = data.get('amount', 0)
                
                if amount:
                    two_fa_service = Financial2FAService(request.user)
                    return two_fa_service.require_2fa_for_amount(amount)
            except:
                pass
        
        # Check user permission level
        if hasattr(request.user, 'profile'):
            return request.user.profile.requires_2fa_for_financial
        
        return False
    
    def _verify_2fa(self, request):
        """Verify 2FA token"""
        two_fa_token = request.headers.get('X-2FA-Token') or request.POST.get('two_fa_token')
        
        if not two_fa_token:
            return False
        
        # Get user's 2FA secret
        if hasattr(request.user, 'twofactor'):
            secret = request.user.twofactor.secret
            two_fa_service = Financial2FAService(request.user)
            verified, message = two_fa_service.verify_code(secret, two_fa_token)
            
            if verified:
                # Log successful 2FA
                FinancialAuditTrail.log_action(
                    action='2FA_VERIFICATION',
                    model_name='User',
                    object_id=request.user.id,
                    user=request.user,
                    request=request,
                    notes='2FA verification successful for financial transaction'
                )
            
            return verified
        
        return False


class SecurePaymentView(SecureFinancialView):
    """Secure payment view with 2FA"""
    
    def post(self, request, *args, **kwargs):
        try:
            import json
            data = json.loads(request.body)
            
            # Validate amount
            amount = Decimal(str(data.get('amount', 0)))
            if amount <= 0:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid amount'
                }, status=400)
            
            # Additional security checks
            if not self._perform_security_checks(request, data):
                return JsonResponse({
                    'success': False,
                    'message': 'Security check failed'
                }, status=403)
            
            # Process payment
            with transaction.atomic():
                # Your payment processing logic here
                
                # Log the transaction
                FinancialAuditTrail.log_action(
                    action='SECURE_PAYMENT',
                    model_name='Payment',
                    object_id='payment_' + str(timezone.now().timestamp()),
                    user=request.user,
                    request=request,
                    notes=f'Secure payment processed: GH₵{amount:.2f}'
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Payment processed securely',
                    'transaction_id': 'TXN_' + str(timezone.now().timestamp())
                })
                
        except Exception as e:
            logger.error(f"Secure payment error: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Payment processing error'
            }, status=500)
    
    def _perform_security_checks(self, request, data):
        """Perform additional security checks"""
        # Check for unusual activity
        if self._detect_unusual_activity(request):
            return False
        
        # Check transaction limits
        if not self._check_transaction_limits(request.user, data.get('amount', 0)):
            return False
        
        # Check IP address (optional)
        if not self._check_ip_address(request):
            return False
        
        return True
    
    def _detect_unusual_activity(self, request):
        """Detect unusual payment activity"""
        # Check for multiple rapid transactions
        recent_transactions = FinancialAuditTrail.objects.filter(
            user=request.user,
            action='SECURE_PAYMENT',
            timestamp__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).count()
        
        return recent_transactions >= 3  # More than 3 transactions in 5 minutes
    
    def _check_transaction_limits(self, user, amount):
        """Check if transaction exceeds user limits"""
        # Get user's daily limit
        daily_limit = Decimal('100000.00')  # Default limit
        
        if hasattr(user, 'profile'):
            daily_limit = user.profile.daily_transaction_limit or daily_limit
        
        # Calculate today's total
        today = timezone.now().date()
        today_total = FinancialAuditTrail.objects.filter(
            user=user,
            action='SECURE_PAYMENT',
            timestamp__date=today
        ).count()  # You'd sum amounts here
        
        return (today_total + Decimal(str(amount))) <= daily_limit
    
    def _check_ip_address(self, request):
        """Check if IP address is suspicious"""
        suspicious_ips = getattr(settings, 'SUSPICIOUS_IPS', [])
        client_ip = self._get_client_ip(request)
        
        return client_ip not in suspicious_ips
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip