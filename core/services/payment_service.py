# core/services/payment_service.py
import logging
import json
import hmac
import hashlib
from decimal import Decimal
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from datetime import datetime
import requests
from requests.exceptions import RequestException, Timeout
from django.db import models
from core.models import Fee, Bill, FeePayment, BillPayment, Student
from core.models.audit import FinancialAuditTrail
from core.utils.financial import FinancialCalculator

logger = logging.getLogger(__name__)


class PaymentService:
    """Main payment service that orchestrates all payment operations"""
    
    def __init__(self, gateway_name=None):
        self.gateway_name = gateway_name or settings.DEFAULT_PAYMENT_GATEWAY
        self.gateway = self._get_gateway_instance()
        self.calculator = FinancialCalculator()
    
    def _get_gateway_instance(self):
        """Get appropriate gateway instance"""
        if self.gateway_name == 'FLUTTERWAVE':
            return FlutterwaveGateway()
        elif self.gateway_name == 'PAYSTACK':
            return PaystackGateway()
        else:
            raise ValueError(f"Unknown gateway: {self.gateway_name}")
    
    def initiate_fee_payment(self, fee_id: int, user, redirect_url=None):
        """Initiate payment for a specific fee"""
        try:
            fee = Fee.objects.select_related('student', 'category').get(pk=fee_id)
            student = fee.student
            
            # Validate fee can be paid
            if not fee.can_accept_payment():
                return {
                    'success': False,
                    'message': 'This fee cannot accept payments (already paid or cancelled)'
                }
            
            # Prepare payment data
            amount = fee.balance
            description = f"{fee.category.get_name_display()} - Term {fee.term} {fee.academic_year}"
            
            customer_data = {
                'student_id': student.student_id,
                'name': student.get_full_name(),
                'email': student.parent_email or user.email,
                'phone': student.parent_phone or '',
            }
            
            metadata = {
                'fee_id': fee.id,
                'student_id': student.id,
                'user_id': user.id,
                'payment_type': 'fee',
                'academic_year': fee.academic_year,
                'term': fee.term
            }
            
            # Initiate payment with gateway
            result = self.gateway.charge(
                amount=amount,
                currency='GHS',
                customer_data=customer_data,
                redirect_url=redirect_url or self._get_default_redirect_url(),
                description=description,
                metadata=metadata
            )
            
            if result['success']:
                # Create pending payment record
                PendingPayment.objects.create(
                    reference=result['transaction_id'],
                    fee=fee,
                    amount=amount,
                    gateway=self.gateway_name,
                    initiated_by=user,
                    metadata=metadata
                )
                
                # Log initiation
                FinancialAuditTrail.log_action(
                    action='PAYMENT_INITIATED',
                    model_name='Fee',
                    object_id=fee.id,
                    user=user,
                    notes=f'Payment initiated via {self.gateway_name} - Ref: {result["transaction_id"]}'
                )
            
            return result
            
        except Fee.DoesNotExist:
            return {'success': False, 'message': 'Fee not found'}
        except Exception as e:
            logger.error(f"Error initiating fee payment: {str(e)}")
            return {'success': False, 'message': 'Payment initiation failed'}
    
    def initiate_bill_payment(self, bill_id: int, user, redirect_url=None):
        """Initiate payment for a bill"""
        try:
            bill = Bill.objects.select_related('student').get(pk=bill_id)
            student = bill.student
            
            if not bill.can_accept_payment():
                return {
                    'success': False,
                    'message': 'This bill cannot accept payments'
                }
            
            amount = bill.balance
            description = f"Bill #{bill.bill_number} - {bill.academic_year} Term {bill.term}"
            
            customer_data = {
                'student_id': student.student_id,
                'name': student.get_full_name(),
                'email': student.parent_email or user.email,
                'phone': student.parent_phone or '',
            }
            
            metadata = {
                'bill_id': bill.id,
                'student_id': student.id,
                'user_id': user.id,
                'payment_type': 'bill',
                'bill_number': bill.bill_number
            }
            
            result = self.gateway.charge(
                amount=amount,
                currency='GHS',
                customer_data=customer_data,
                redirect_url=redirect_url or self._get_default_redirect_url(),
                description=description,
                metadata=metadata
            )
            
            if result['success']:
                PendingPayment.objects.create(
                    reference=result['transaction_id'],
                    bill=bill,
                    amount=amount,
                    gateway=self.gateway_name,
                    initiated_by=user,
                    metadata=metadata
                )
                
                FinancialAuditTrail.log_action(
                    action='PAYMENT_INITIATED',
                    model_name='Bill',
                    object_id=bill.id,
                    user=user,
                    notes=f'Bill payment initiated via {self.gateway_name}'
                )
            
            return result
            
        except Bill.DoesNotExist:
            return {'success': False, 'message': 'Bill not found'}
        except Exception as e:
            logger.error(f"Error initiating bill payment: {str(e)}")
            return {'success': False, 'message': 'Payment initiation failed'}
    
    def verify_and_process_payment(self, transaction_id: str, gateway_name=None):
        """Verify and process a payment"""
        try:
            # Get pending payment
            pending = PendingPayment.objects.select_related('fee', 'bill').get(
                reference=transaction_id
            )
            
            # Use specified gateway or default
            gateway = self.gateway
            if gateway_name:
                gateway = FlutterwaveGateway() if gateway_name == 'FLUTTERWAVE' else PaystackGateway()
            
            # Verify with gateway
            verification = gateway.verify_transaction(transaction_id)
            
            if verification.get('verified') and verification.get('status') == 'successful':
                # Process the payment
                if pending.fee:
                    return self._process_fee_payment(pending, verification, gateway)
                else:
                    return self._process_bill_payment(pending, verification, gateway)
            else:
                # Mark as failed
                pending.status = 'failed'
                pending.save()
                
                return {
                    'success': False,
                    'message': verification.get('message', 'Payment verification failed')
                }
                
        except PendingPayment.DoesNotExist:
            return {'success': False, 'message': 'Pending payment not found'}
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            return {'success': False, 'message': 'Payment processing failed'}
    
    def _process_fee_payment(self, pending, verification, gateway):
        """Process fee payment"""
        fee = pending.fee
        student = fee.student
        
        with transaction.atomic():
            # Create payment record
            payment = FeePayment.objects.create(
                fee=fee,
                amount=pending.amount,
                payment_mode='online',
                payment_date=timezone.now(),
                receipt_number=self._generate_receipt_number('FEE'),
                recorded_by=pending.initiated_by,
                notes=f"Online payment via {gateway.name} - Ref: {pending.reference}",
                bank_reference=pending.reference,
                is_confirmed=True
            )
            
            # Update fee
            fee.amount_paid += pending.amount
            fee.save()
            
            # Update pending payment
            pending.status = 'completed'
            pending.completed_at = timezone.now()
            pending.save()
            
            # Log successful payment
            FinancialAuditTrail.log_action(
                action='PAYMENT_COMPLETED',
                model_name='FeePayment',
                object_id=payment.id,
                user=pending.initiated_by,
                notes=f'Online payment completed - Amount: GH₵{pending.amount:.2f}'
            )
            
            # Generate receipt
            receipt_data = self._prepare_receipt_data(payment, verification, 'fee')
            
            return {
                'success': True,
                'message': 'Payment processed successfully',
                'payment_id': payment.id,
                'receipt_data': receipt_data,
                'student_name': student.get_full_name(),
                'amount': pending.amount
            }
    
    def _process_bill_payment(self, pending, verification, gateway):
        """Process bill payment"""
        bill = pending.bill
        
        with transaction.atomic():
            # Create bill payment
            payment = BillPayment.objects.create(
                bill=bill,
                amount=pending.amount,
                payment_mode='online',
                payment_date=timezone.now().date(),
                reference_number=pending.reference,
                recorded_by=pending.initiated_by,
                notes=f"Online payment via {gateway.name}"
            )
            
            # Update bill
            bill.update_status()
            
            # Update pending
            pending.status = 'completed'
            pending.completed_at = timezone.now()
            pending.save()
            
            FinancialAuditTrail.log_action(
                action='PAYMENT_COMPLETED',
                model_name='BillPayment',
                object_id=payment.id,
                user=pending.initiated_by,
                notes=f'Bill payment completed - Amount: GH₵{pending.amount:.2f}'
            )
            
            receipt_data = self._prepare_receipt_data(payment, verification, 'bill')
            
            return {
                'success': True,
                'message': 'Bill payment processed successfully',
                'payment_id': payment.id,
                'receipt_data': receipt_data,
                'student_name': bill.student.get_full_name(),
                'amount': pending.amount
            }
    
    def _generate_receipt_number(self, prefix):
        """Generate unique receipt number"""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_str = hashlib.md5(str(timezone.now().timestamp()).encode()).hexdigest()[:6]
        return f"{prefix}-{timestamp}-{random_str}"
    
    def _prepare_receipt_data(self, payment, verification, payment_type):
        """Prepare data for receipt generation"""
        if payment_type == 'fee':
            student = payment.fee.student
            description = f"{payment.fee.category.get_name_display()} - Term {payment.fee.term}"
        else:
            student = payment.bill.student
            description = f"Bill #{payment.bill.bill_number}"
        
        return {
            'receipt_number': getattr(payment, 'receipt_number', getattr(payment, 'reference_number', '')),
            'transaction_id': verification.get('transaction_id', ''),
            'payment_date': payment.payment_date,
            'amount': payment.amount,
            'description': description,
            'payment_method': 'Online Payment',
            'gateway': self.gateway_name,
            'student': {
                'name': student.get_full_name(),
                'student_id': student.student_id,
                'class': student.get_class_level_display()
            },
            'verification_data': verification
        }
    
    def _get_default_redirect_url(self):
        """Get default redirect URL"""
        from django.urls import reverse
        return f"{settings.SITE_URL}{reverse('payment_callback')}"
    
    def handle_webhook(self, request, gateway_name):
        """Handle payment webhook"""
        try:
            if gateway_name == 'FLUTTERWAVE':
                gateway = FlutterwaveGateway()
            elif gateway_name == 'PAYSTACK':
                gateway = PaystackGateway()
            else:
                return False
            
            # Verify webhook
            if not gateway.verify_webhook(request):
                logger.warning(f"Invalid webhook signature from {gateway_name}")
                return False
            
            # Parse payload
            payload = json.loads(request.body)
            event_type = payload.get('event')
            
            # Process based on event
            if event_type == 'charge.completed':
                transaction_id = payload.get('data', {}).get('tx_ref')
                if transaction_id:
                    # Verify and process if not already processed
                    self.verify_and_process_payment(transaction_id, gateway_name)
            
            logger.info(f"Webhook processed: {event_type}")
            return True
            
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            return False


# Concrete Gateway Implementations
class FlutterwaveGateway:
    """Flutterwave gateway implementation"""
    
    def __init__(self):
        config = settings.PAYMENT_GATEWAYS['FLUTTERWAVE']
        self.secret_key = config['SECRET_KEY']
        self.public_key = config['PUBLIC_KEY']
        self.encryption_key = config['ENCRYPTION_KEY']
        self.webhook_hash = config['WEBHOOK_HASH']
        self.base_url = config['BASE_URL']
        self.timeout = 30
        self.max_retries = 3
    
    def charge(self, amount, currency, customer_data, **kwargs):
        """Initiate payment"""
        try:
            tx_ref = self._generate_transaction_reference()
            
            payload = {
                'tx_ref': tx_ref,
                'amount': str(amount),
                'currency': currency,
                'redirect_url': kwargs.get('redirect_url'),
                'payment_options': 'card,mobilemoneyghana,banktransfer',
                'customer': {
                    'email': customer_data.get('email'),
                    'phonenumber': customer_data.get('phone'),
                    'name': customer_data.get('name')
                },
                'customizations': {
                    'title': kwargs.get('school_name', settings.SCHOOL_INFO['NAME']),
                    'description': kwargs.get('description', 'School Fees Payment'),
                    'logo': kwargs.get('logo_url', settings.SCHOOL_INFO.get('LOGO_URL', ''))
                },
                'meta': kwargs.get('metadata', {})
            }
            
            headers = {
                'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/json'
            }
            
            response = self._make_request('POST', '/payments', json=payload, headers=headers)
            data = response.json()
            
            if response.status_code == 200 and data.get('status') == 'success':
                return {
                    'success': True,
                    'transaction_id': tx_ref,
                    'payment_url': data['data']['link'],
                    'message': 'Payment initiated successfully',
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'message': data.get('message', 'Payment initiation failed'),
                    'data': data
                }
                
        except Exception as e:
            logger.error(f"Flutterwave charge error: {str(e)}")
            return {
                'success': False,
                'message': 'Payment service error'
            }
    
    def verify_transaction(self, transaction_id):
        """Verify transaction"""
        try:
            headers = {
                'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/json'
            }
            
            response = self._make_request('GET', f'/transactions/verify_by_reference?tx_ref={transaction_id}', headers=headers)
            data = response.json()
            
            if response.status_code == 200 and data.get('status') == 'success':
                return {
                    'verified': True,
                    'status': data['data']['status'],
                    'amount': Decimal(str(data['data']['amount'])),
                    'currency': data['data']['currency'],
                    'transaction_id': transaction_id,
                    'data': data
                }
            else:
                return {
                    'verified': False,
                    'message': data.get('message', 'Verification failed'),
                    'data': data
                }
                
        except Exception as e:
            logger.error(f"Flutterwave verification error: {str(e)}")
            return {
                'verified': False,
                'message': 'Verification service error'
            }
    
    def verify_webhook(self, request):
        """Verify webhook signature"""
        signature = request.headers.get('verif-hash')
        return signature == self.webhook_hash
    
    def _generate_transaction_reference(self):
        """Generate transaction reference"""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_str = hashlib.md5(str(timezone.now().timestamp()).encode()).hexdigest()[:8]
        return f"SCHOOL_{timestamp}_{random_str}"
    
    def _make_request(self, method, endpoint, **kwargs):
        """Make HTTP request with retry"""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method, 
                    url, 
                    timeout=self.timeout, 
                    **kwargs
                )
                response.raise_for_status()
                return response
            except (RequestException, Timeout) as e:
                if attempt == self.max_retries - 1:
                    raise
                logger.warning(f"Request attempt {attempt + 1} failed: {str(e)}")
                time.sleep(1)
        
        raise RequestException("Max retries exceeded")


class PaystackGateway:
    """Paystack gateway implementation (similar pattern)"""
    # Implementation follows same pattern as Flutterwave
    # Would need to adapt to Paystack API
    
    def charge(self, amount, currency, customer_data, **kwargs):
        # Paystack-specific implementation
        pass
    
    def verify_transaction(self, transaction_id):
        pass
    
    def verify_webhook(self, request):
        pass


# Pending Payment Model (Add to models.py)
class PendingPayment(models.Model):
    """Track pending online payments"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    reference = models.CharField(max_length=100, unique=True)
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, null=True, blank=True)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gateway = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Pending: {self.reference} - GH₵{self.amount}"