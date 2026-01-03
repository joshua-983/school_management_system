import logging
import hashlib
import hmac
import json
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from datetime import datetime
import requests
from requests.exceptions import RequestException, Timeout

logger = logging.getLogger(__name__)


class PaymentGateway(ABC):
    """Abstract base class for payment gateways"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.timeout = 30  # seconds
        self.max_retries = 3
        self.retry_delay = 1  # second
    
    @abstractmethod
    def charge(self, amount: Decimal, currency: str, 
               customer_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Process a payment"""
        pass
    
    @abstractmethod
    def refund(self, transaction_id: str, 
               amount: Optional[Decimal] = None) -> Dict[str, Any]:
        """Process a refund"""
        pass
    
    @abstractmethod
    def verify_webhook(self, request) -> bool:
        """Verify webhook signature"""
        pass
    
    def format_amount(self, amount: Decimal, currency: str) -> int:
        """Convert Decimal amount to smallest currency unit (e.g., pesewas)"""
        if currency.upper() in ['GHS', 'USD', 'EUR', 'GBP']:
            return int(amount * 100)
        return int(amount)
    
    def log_transaction(self, transaction_type: str, data: Dict[str, Any], 
                       success: bool, error: str = None):
        """Log payment transaction for audit"""
        log_data = {
            'gateway': self.name,
            'type': transaction_type,
            'timestamp': timezone.now().isoformat(),
            'success': success,
            'data': data,
            'error': error
        }
        
        if success:
            logger.info(f"Payment {transaction_type} successful: {json.dumps(log_data)}")
        else:
            logger.error(f"Payment {transaction_type} failed: {json.dumps(log_data)}")
        
        # Log to audit trail
        from core.models.audit import FinancialAuditTrail
        FinancialAuditTrail.log_action(
            action='PAYMENT',
            model_name='PaymentGateway',
            object_id=data.get('reference', 'unknown'),
            user=None,  # System action
            notes=f"{transaction_type} via {self.name} - {'Success' if success else 'Failed'}: {error or 'No error'}"
        )


class FlutterwaveGateway(PaymentGateway):
    """Flutterwave payment gateway implementation for Ghana"""
    
    def __init__(self):
        super().__init__()
        self.api_key = getattr(settings, 'FLUTTERWAVE_SECRET_KEY', '')
        self.public_key = getattr(settings, 'FLUTTERWAVE_PUBLIC_KEY', '')
        self.base_url = "https://api.flutterwave.com/v3"
        self.encryption_key = getattr(settings, 'FLUTTERWAVE_ENCRYPTION_KEY', '')
        
        if not self.api_key:
            logger.warning("Flutterwave API key not configured")
    
    def charge(self, amount: Decimal, currency: str, 
               customer_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Process payment via Flutterwave
        Returns: {'success': bool, 'transaction_id': str, 'message': str, 'data': dict}
        """
        # Validate amount
        if amount <= Decimal('0.00'):
            return {
                'success': False,
                'message': 'Amount must be greater than zero',
                'transaction_id': None
            }
        
        # Prepare payload
        payload = {
            'tx_ref': self._generate_transaction_reference(),
            'amount': float(amount),
            'currency': currency.upper(),
            'redirect_url': kwargs.get('redirect_url', 
                                     f"{settings.SITE_URL}/payment/callback"),
            'customer': {
                'email': customer_data.get('email', ''),
                'phonenumber': customer_data.get('phone', ''),
                'name': customer_data.get('name', '')
            },
            'customizations': {
                'title': kwargs.get('school_name', 'School Fees Payment'),
                'description': kwargs.get('description', 'School Fees Payment'),
                'logo': kwargs.get('logo_url', '')
            },
            'meta': {
                'student_id': customer_data.get('student_id'),
                'purpose': 'school_fees',
                'term': kwargs.get('term'),
                'academic_year': kwargs.get('academic_year')
            }
        }
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # Make API request with retry logic
            response = self._make_request_with_retry(
                'POST',
                f'{self.base_url}/payments',
                json=payload,
                headers=headers
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('status') == 'success':
                result = {
                    'success': True,
                    'transaction_id': response_data['data']['tx_ref'],
                    'flw_ref': response_data['data']['flw_ref'],
                    'payment_url': response_data['data']['link'],
                    'message': 'Payment initiated successfully',
                    'data': response_data
                }
                
                self.log_transaction('CHARGE', result, True)
                return result
            else:
                error_msg = response_data.get('message', 'Payment failed')
                result = {
                    'success': False,
                    'transaction_id': payload['tx_ref'],
                    'message': error_msg,
                    'data': response_data
                }
                
                self.log_transaction('CHARGE', result, False, error_msg)
                return result
                
        except RequestException as e:
            error_msg = f"Network error: {str(e)}"
            logger.error(error_msg)
            
            result = {
                'success': False,
                'transaction_id': payload['tx_ref'],
                'message': 'Payment service temporarily unavailable',
                'data': {'error': str(e)}
            }
            
            self.log_transaction('CHARGE', result, False, error_msg)
            return result
    
    def refund(self, transaction_id: str, 
               amount: Optional[Decimal] = None) -> Dict[str, Any]:
        """Process refund via Flutterwave"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {}
            if amount:
                payload['amount'] = float(amount)
            
            response = requests.post(
                f'{self.base_url}/transactions/{transaction_id}/refund',
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('status') == 'success':
                result = {
                    'success': True,
                    'refund_id': response_data['data']['id'],
                    'message': 'Refund processed successfully',
                    'data': response_data
                }
                
                self.log_transaction('REFUND', result, True)
                return result
            else:
                error_msg = response_data.get('message', 'Refund failed')
                result = {
                    'success': False,
                    'message': error_msg,
                    'data': response_data
                }
                
                self.log_transaction('REFUND', result, False, error_msg)
                return result
                
        except RequestException as e:
            error_msg = f"Refund network error: {str(e)}"
            logger.error(error_msg)
            
            result = {
                'success': False,
                'message': 'Refund service temporarily unavailable',
                'data': {'error': str(e)}
            }
            
            self.log_transaction('REFUND', result, False, error_msg)
            return result
    
    def verify_webhook(self, request) -> bool:
        """Verify Flutterwave webhook signature"""
        secret_hash = getattr(settings, 'FLUTTERWAVE_WEBHOOK_HASH', '')
        if not secret_hash:
            logger.warning("Flutterwave webhook hash not configured")
            return False
        
        signature = request.headers.get('verif-hash')
        if not signature:
            return False
        
        return signature == secret_hash
    
    def verify_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Verify transaction status"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'{self.base_url}/transactions/{transaction_id}/verify',
                headers=headers,
                timeout=self.timeout
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('status') == 'success':
                return {
                    'verified': True,
                    'amount': Decimal(str(response_data['data']['amount'])),
                    'currency': response_data['data']['currency'],
                    'status': response_data['data']['status'],
                    'customer': response_data['data']['customer'],
                    'data': response_data
                }
            else:
                return {
                    'verified': False,
                    'message': response_data.get('message', 'Verification failed'),
                    'data': response_data
                }
                
        except RequestException as e:
            logger.error(f"Verification error: {str(e)}")
            return {
                'verified': False,
                'message': f'Verification error: {str(e)}'
            }
    
    def _generate_transaction_reference(self) -> str:
        """Generate unique transaction reference"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_str = hashlib.md5(str(timezone.now().timestamp()).encode()).hexdigest()[:8]
        return f"SCHOOL_{timestamp}_{random_str}"
    
    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic"""
        for attempt in range(self.max_retries):
            try:
                response = requests.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response
            except (RequestException, Timeout) as e:
                if attempt == self.max_retries - 1:
                    raise
                logger.warning(f"Request attempt {attempt + 1} failed: {str(e)}")
                time.sleep(self.retry_delay)
        
        raise RequestException("Max retries exceeded")


class PaystackGateway(PaymentGateway):
    """Paystack payment gateway implementation"""
    
    def __init__(self):
        super().__init__()
        self.api_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        self.public_key = getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
        self.base_url = "https://api.paystack.co"
    
    def charge(self, amount: Decimal, currency: str, 
               customer_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Process payment via Paystack (Ghana/Nigeria)"""
        # Similar implementation to Flutterwave
        # Implement based on Paystack API documentation
        pass
    
    def refund(self, transaction_id: str, 
               amount: Optional[Decimal] = None) -> Dict[str, Any]:
        """Process refund via Paystack"""
        pass
    
    def verify_webhook(self, request) -> bool:
        """Verify Paystack webhook signature"""
        pass


class PaymentGatewayFactory:
    """Factory to create payment gateway instances"""
    
    @staticmethod
    def get_gateway(gateway_name: str = None) -> PaymentGateway:
        """Get payment gateway instance"""
        if not gateway_name:
            gateway_name = getattr(settings, 'DEFAULT_PAYMENT_GATEWAY', 'flutterwave')
        
        gateways = {
            'flutterwave': FlutterwaveGateway,
            'paystack': PaystackGateway,
        }
        
        gateway_class = gateways.get(gateway_name.lower())
        if not gateway_class:
            raise ValueError(f"Unknown payment gateway: {gateway_name}")
        
        return gateway_class()