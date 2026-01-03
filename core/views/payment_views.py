# core/views/payment_views.py
import logging
import json
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.urls import reverse

from core.services.payment_gateways import PaymentGatewayFactory
from core.models import Fee, Bill, FeePayment, BillPayment, Student
from core.models.audit import FinancialAuditTrail
from core.utils.financial import FinancialCalculator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class InitiateOnlinePaymentView(LoginRequiredMixin, View):
    """Initiate online payment for fees or bills"""
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            payment_type = data.get('type')  # 'fee' or 'bill'
            item_id = data.get('item_id')
            gateway = data.get('gateway', 'flutterwave')
            
            # Validate input
            if payment_type not in ['fee', 'bill']:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid payment type'
                }, status=400)
            
            # Get payment gateway
            try:
                payment_gateway = PaymentGatewayFactory.get_gateway(gateway)
            except ValueError as e:
                return JsonResponse({
                    'success': False,
                    'message': str(e)
                }, status=400)
            
            # Get payment item
            if payment_type == 'fee':
                payment_item = get_object_or_404(Fee, pk=item_id)
                amount = payment_item.balance
                student = payment_item.student
                description = f"Fee Payment - {payment_item.category.get_name_display()}"
            else:  # bill
                payment_item = get_object_or_404(Bill, pk=item_id)
                amount = payment_item.balance
                student = payment_item.student
                description = f"Bill Payment - {payment_item.bill_number}"
            
            # Validate amount
            if amount <= Decimal('0.00'):
                return JsonResponse({
                    'success': False,
                    'message': 'No amount due for payment'
                })
            
            # Prepare customer data
            customer_data = {
                'student_id': student.student_id,
                'name': student.get_full_name(),
                'email': student.parent_email or request.user.email,
                'phone': student.parent_phone or '',
            }
            
            # Prepare metadata
            metadata = {
                'student_id': student.id,
                'item_type': payment_type,
                'item_id': item_id,
                'user_id': request.user.id,
                'school_id': getattr(settings, 'SCHOOL_ID', ''),
            }
            
            # Initiate payment
            result = payment_gateway.charge(
                amount=amount,
                currency='GHS',
                customer_data=customer_data,
                redirect_url=request.build_absolute_uri(
                    reverse('payment_callback', kwargs={'gateway': gateway})
                ),
                description=description,
                metadata=metadata
            )
            
            if result['success']:
                # Store pending payment in session or database
                request.session['pending_payment'] = {
                    'transaction_id': result['transaction_id'],
                    'item_type': payment_type,
                    'item_id': item_id,
                    'amount': str(amount),
                    'gateway': gateway,
                    'timestamp': timezone.now().isoformat()
                }
                request.session.modified = True
                
                # Log initiation
                FinancialAuditTrail.log_action(
                    action='PAYMENT',
                    model_name='OnlinePayment',
                    object_id=result['transaction_id'],
                    user=request.user,
                    request=request,
                    notes=f'Online payment initiated via {gateway} for {payment_type} {item_id}'
                )
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error initiating payment: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Internal server error'
            }, status=500)


class PaymentCallbackView(View):
    """Handle payment callback from gateway"""
    
    def get(self, request, gateway, *args, **kwargs):
        try:
            transaction_id = request.GET.get('transaction_id')
            status = request.GET.get('status')
            
            if not transaction_id:
                return self._render_payment_result(
                    request, False, 'No transaction ID provided'
                )
            
            # Get payment gateway
            payment_gateway = PaymentGatewayFactory.get_gateway(gateway)
            
            # Verify transaction
            verification = payment_gateway.verify_transaction(transaction_id)
            
            if verification.get('verified') and verification.get('status') == 'successful':
                # Process successful payment
                return self._process_successful_payment(
                    request, transaction_id, payment_gateway, verification
                )
            else:
                # Payment failed
                return self._render_payment_result(
                    request, False,
                    verification.get('message', 'Payment verification failed')
                )
                
        except Exception as e:
            logger.error(f"Payment callback error: {str(e)}")
            return self._render_payment_result(
                request, False, 'Payment processing error'
            )
    
    def _process_successful_payment(self, request, transaction_id, gateway, verification):
        """Process successful payment"""
        # Get pending payment from session
        pending_payment = request.session.get('pending_payment', {})
        
        if not pending_payment or pending_payment.get('transaction_id') != transaction_id:
            return self._render_payment_result(
                request, False, 'Invalid or expired payment session'
            )
        
        item_type = pending_payment.get('item_type')
        item_id = pending_payment.get('item_id')
        amount = Decimal(pending_payment.get('amount', '0'))
        
        try:
            with transaction.atomic():
                if item_type == 'fee':
                    payment_item = Fee.objects.select_for_update().get(pk=item_id)
                    
                    # Create payment record
                    fee_payment = FeePayment.objects.create(
                        fee=payment_item,
                        amount=amount,
                        payment_mode='online',
                        payment_date=timezone.now(),
                        receipt_number=f"ONLINE-{transaction_id[:10]}",
                        recorded_by=request.user if request.user.is_authenticated else None,
                        notes=f"Online payment via {gateway.name} - Ref: {transaction_id}",
                        bank_reference=transaction_id,
                        is_confirmed=True
                    )
                    
                    # Update fee status
                    payment_item.amount_paid += amount
                    payment_item.save()
                    
                    payment_record = fee_payment
                    
                else:  # bill
                    payment_item = Bill.objects.select_for_update().get(pk=item_id)
                    
                    # Create bill payment
                    bill_payment = BillPayment.objects.create(
                        bill=payment_item,
                        amount=amount,
                        payment_mode='online',
                        payment_date=timezone.now().date(),
                        reference_number=transaction_id,
                        recorded_by=request.user if request.user.is_authenticated else None,
                        notes=f"Online payment via {gateway.name}"
                    )
                    
                    # Update bill status
                    payment_item.update_status()
                    
                    payment_record = bill_payment
                
                # Clear pending payment from session
                if 'pending_payment' in request.session:
                    del request.session['pending_payment']
                
                # Log successful payment
                FinancialAuditTrail.log_action(
                    action='PAYMENT',
                    model_name=payment_record.__class__.__name__,
                    object_id=payment_record.id,
                    user=request.user if request.user.is_authenticated else None,
                    request=request,
                    notes=f'Online payment completed via {gateway.name} - Amount: GH₵{amount}'
                )
                
                # Generate receipt
                receipt_data = self._prepare_receipt_data(payment_record, verification)
                
                return self._render_payment_result(
                    request, True, 'Payment successful!',
                    receipt_data=receipt_data,
                    payment_id=payment_record.id
                )
                
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            return self._render_payment_result(
                request, False, f'Payment processing error: {str(e)}'
            )
    
    def _prepare_receipt_data(self, payment_record, verification):
        """Prepare data for receipt generation"""
        if hasattr(payment_record, 'fee'):
            student = payment_record.fee.student
            item_type = 'fee'
        else:
            student = payment_record.bill.student
            item_type = 'bill'
        
        return {
            'receipt_number': getattr(payment_record, 'receipt_number', 
                                     getattr(payment_record, 'reference_number', 'N/A')),
            'transaction_id': verification.get('data', {}).get('tx_ref', 'N/A'),
            'payment_date': payment_record.payment_date,
            'amount': payment_record.amount,
            'payment_method': 'Online Payment',
            'student': {
                'name': student.get_full_name(),
                'student_id': student.student_id,
                'class': student.get_class_level_display()
            },
            'verification_data': verification
        }
    
    def _render_payment_result(self, request, success, message, 
                              receipt_data=None, payment_id=None):
        """Render payment result page"""
        from django.shortcuts import render
        
        context = {
            'success': success,
            'message': message,
            'receipt_data': receipt_data,
            'payment_id': payment_id,
            'site_url': getattr(settings, 'SITE_URL', ''),
        }
        
        return render(request, 'core/finance/payment/payment_result.html', context)

# Add to core/views/payment_views.py (at the end, before the last line)

class OutstandingFeesAPIView(LoginRequiredMixin, View):
    """API endpoint for outstanding fees"""
    
    def get(self, request, *args, **kwargs):
        try:
            # Get student
            if hasattr(request.user, 'student'):
                student = request.user.student
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Student profile not found'
                }, status=404)
            
            # Get outstanding fees
            outstanding_fees = Fee.objects.filter(
                student=student,
                status__in=['unpaid', 'partial']
            ).select_related('category').order_by('due_date')
            
            fees_data = []
            for fee in outstanding_fees:
                fees_data.append({
                    'id': fee.id,
                    'category_display': fee.category.get_name_display(),
                    'term': fee.term,
                    'due_date': fee.due_date.strftime('%Y-%m-%d') if fee.due_date else '',
                    'balance': float(fee.balance),
                    'description': f"{fee.category.get_name_display()} - Term {fee.term}"
                })
            
            return JsonResponse({
                'success': True,
                'fees': fees_data,
                'total_outstanding': float(sum(fee.balance for fee in outstanding_fees))
            })
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Outstanding fees API error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Unable to fetch outstanding fees'
            }, status=500)
@method_decorator(csrf_exempt, name='dispatch')
class PaymentWebhookView(View):
    """Handle payment webhooks from gateways"""
    
    def post(self, request, gateway):
        try:
            # Get payment gateway
            payment_gateway = PaymentGatewayFactory.get_gateway(gateway)
            
            # Verify webhook signature
            if not payment_gateway.verify_webhook(request):
                logger.warning(f"Invalid webhook signature from {gateway}")
                return HttpResponse(status=401)
            
            # Parse webhook data
            payload = json.loads(request.body)
            
            # Log webhook receipt
            logger.info(f"Webhook received from {gateway}: {json.dumps(payload)}")
            
            # Process based on gateway
            if gateway == 'flutterwave':
                return self._process_flutterwave_webhook(payload, payment_gateway)
            elif gateway == 'paystack':
                return self._process_paystack_webhook(payload, payment_gateway)
            
            return HttpResponse(status=200)
            
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            return HttpResponse(status=500)
    
    def _process_flutterwave_webhook(self, payload, gateway):
        """Process Flutterwave webhook"""
        event_type = payload.get('event')
        data = payload.get('data', {})
        
        if event_type == 'charge.completed':
            # Payment completed
            transaction_id = data.get('tx_ref')
            status = data.get('status')
            amount = Decimal(str(data.get('amount', 0)))
            
            # Verify and process payment
            verification = gateway.verify_transaction(data.get('id', ''))
            
            if verification.get('verified') and verification.get('status') == 'successful':
                # Update your database here
                # This is a backup in case callback fails
                logger.info(f"Webhook confirmed payment: {transaction_id}")
                
                # Log webhook action
                FinancialAuditTrail.log_action(
                    action='WEBHOOK',
                    model_name='PaymentGateway',
                    object_id=transaction_id,
                    user=None,
                    notes=f'Webhook confirmed payment: {transaction_id} - Amount: GH₵{amount}'
                )
        
        return HttpResponse(status=200)
    
    def _process_paystack_webhook(self, payload, gateway):
        """Process Paystack webhook"""
        # Implement based on Paystack webhook format
        return HttpResponse(status=200)


class PaymentHistoryView(LoginRequiredMixin, View):
    """View payment history for a student"""
    
    def get(self, request, student_id=None):
        if student_id:
            student = get_object_or_404(Student, pk=student_id)
        elif hasattr(request.user, 'student'):
            student = request.user.student
        else:
            return JsonResponse({
                'success': False,
                'message': 'Student not found'
            }, status=404)
        
        # Get fee payments
        fee_payments = FeePayment.objects.filter(
            fee__student=student
        ).select_related('fee', 'fee__category').order_by('-payment_date')[:50]
        
        # Get bill payments
        bill_payments = BillPayment.objects.filter(
            bill__student=student
        ).select_related('bill').order_by('-payment_date')[:50]
        
        # Format data
        payments = []
        
        for payment in fee_payments:
            payments.append({
                'type': 'fee',
                'date': payment.payment_date,
                'amount': payment.amount,
                'method': payment.get_payment_mode_display(),
                'description': f"{payment.fee.category.get_name_display()} - Term {payment.fee.term}",
                'receipt_number': payment.receipt_number,
                'confirmed': payment.is_confirmed
            })
        
        for payment in bill_payments:
            payments.append({
                'type': 'bill',
                'date': payment.payment_date,
                'amount': payment.amount,
                'method': payment.get_payment_mode_display(),
                'description': f"Bill #{payment.bill.bill_number}",
                'receipt_number': payment.reference_number or f"BILL-{payment.id}",
                'confirmed': True
            })
        
        # Sort by date
        payments.sort(key=lambda x: x['date'], reverse=True)
        
        # Calculate statistics
        total_paid = sum(p['amount'] for p in payments)
        online_payments = sum(p['amount'] for p in payments if p['method'] == 'Online')
        
        return JsonResponse({
            'success': True,
            'student': {
                'id': student.id,
                'name': student.get_full_name(),
                'student_id': student.student_id,
                'class': student.get_class_level_display()
            },
            'payments': payments[:30],  # Limit for display
            'statistics': {
                'total_payments': len(payments),
                'total_amount': total_paid,
                'online_amount': online_payments,
                'online_percentage': (online_payments / total_paid * 100) if total_paid > 0 else 0
            }
        })