import logging
import json
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.db import transaction
from django.views.generic import TemplateView
from django.conf import settings
from core.services.payment_service import PaymentService
from core.models import Fee, Bill, Student
from core.models.audit import FinancialAuditTrail
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class InitiatePaymentView(LoginRequiredMixin, View):
    """Initiate online payment"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            payment_type = data.get('type')  # 'fee' or 'bill'
            item_id = data.get('item_id')
            gateway = data.get('gateway', settings.DEFAULT_PAYMENT_GATEWAY)
            
            # Validate
            if payment_type not in ['fee', 'bill']:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid payment type'
                }, status=400)
            
            # Create payment service
            payment_service = PaymentService(gateway)
            
            # Build redirect URL
            redirect_url = request.build_absolute_uri(
                reverse('payment_callback', kwargs={'gateway': gateway.lower()})
            )
            
            # Initiate payment
            if payment_type == 'fee':
                result = payment_service.initiate_fee_payment(
                    fee_id=item_id,
                    user=request.user,
                    redirect_url=redirect_url
                )
            else:
                result = payment_service.initiate_bill_payment(
                    bill_id=item_id,
                    user=request.user,
                    redirect_url=redirect_url
                )
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Payment initiation error: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Payment initiation failed'
            }, status=500)


class PaymentCallbackView(View):
    """Handle payment callback from gateway"""
    
    def get(self, request, gateway):
        transaction_id = request.GET.get('transaction_id') or request.GET.get('trxref')
        status = request.GET.get('status')
        
        if not transaction_id:
            return render(request, 'core/finance/payment/error.html', {
                'error': 'No transaction ID provided',
                'school_name': settings.SCHOOL_INFO['NAME']
            })
        
        # Convert gateway name to uppercase
        gateway_upper = gateway.upper()
        
        # Verify and process payment
        payment_service = PaymentService(gateway_upper)
        result = payment_service.verify_and_process_payment(transaction_id, gateway_upper)
        
        if result['success']:
            # Success page
            return render(request, 'core/finance/payment/success.html', {
                'payment': result,
                'school_name': settings.SCHOOL_INFO['NAME'],
                'school_email': settings.SCHOOL_INFO['EMAIL'],
                'receipt_data': result.get('receipt_data')
            })
        else:
            # Error page
            return render(request, 'core/finance/payment/error.html', {
                'error': result.get('message', 'Payment failed'),
                'transaction_id': transaction_id,
                'school_name': settings.SCHOOL_INFO['NAME'],
                'contact_email': settings.SCHOOL_INFO['EMAIL']
            })


@method_decorator(csrf_exempt, name='dispatch')
class PaymentWebhookView(View):
    """Handle payment webhooks"""
    
    def post(self, request, gateway):
        gateway_upper = gateway.upper()
        
        try:
            payment_service = PaymentService(gateway_upper)
            success = payment_service.handle_webhook(request, gateway_upper)
            
            if success:
                return HttpResponse(status=200)
            else:
                return HttpResponse(status=400)
                
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return HttpResponse(status=500)


class StudentPaymentHistoryView(LoginRequiredMixin, View):
    """View payment history for a student"""
    
    def get(self, request, student_id=None):
        if student_id:
            student = get_object_or_404(Student, pk=student_id)
            # Check permission
            if not (request.user.is_staff or 
                   (hasattr(request.user, 'student') and request.user.student == student)):
                return JsonResponse({
                    'success': False,
                    'message': 'Permission denied'
                }, status=403)
        elif hasattr(request.user, 'student'):
            student = request.user.student
        else:
            return JsonResponse({
                'success': False,
                'message': 'Student not found'
            }, status=404)
        
        # Get payments
        fee_payments = student.fee_payments.select_related('fee__category').order_by('-payment_date')
        bill_payments = student.bill_payments.select_related('bill').order_by('-payment_date')
        
        # Format response
        payments = []
        
        for payment in fee_payments:
            payments.append({
                'id': payment.id,
                'type': 'fee',
                'date': payment.payment_date,
                'amount': float(payment.amount),
                'method': payment.get_payment_mode_display(),
                'description': f"{payment.fee.category.get_name_display()} - Term {payment.fee.term}",
                'receipt_number': payment.receipt_number,
                'confirmed': payment.is_confirmed,
                'online': payment.payment_mode == 'online'
            })
        
        for payment in bill_payments:
            payments.append({
                'id': payment.id,
                'type': 'bill',
                'date': payment.payment_date,
                'amount': float(payment.amount),
                'method': payment.get_payment_mode_display(),
                'description': f"Bill #{payment.bill.bill_number}",
                'receipt_number': payment.reference_number,
                'confirmed': True,
                'online': payment.payment_mode == 'online'
            })
        
        # Sort by date
        payments.sort(key=lambda x: x['date'], reverse=True)
        
        # Calculate statistics
        total_paid = sum(p['amount'] for p in payments)
        online_total = sum(p['amount'] for p in payments if p.get('online'))
        
        return JsonResponse({
            'success': True,
            'student': {
                'id': student.id,
                'name': student.get_full_name(),
                'student_id': student.student_id,
                'class': student.get_class_level_display()
            },
            'payments': payments[:50],  # Limit to 50 most recent
            'statistics': {
                'total_payments': len(payments),
                'total_amount': total_paid,
                'online_amount': online_total,
                'online_percentage': (online_total / total_paid * 100) if total_paid > 0 else 0,
                'average_payment': total_paid / len(payments) if payments else 0
            }
        })


class GeneratePaymentReceiptView(LoginRequiredMixin, View):
    """Generate PDF receipt for payment"""
    
    def get(self, request, payment_id, payment_type):
        from core.services.receipt_generator import ProfessionalReceiptGenerator
        
        if payment_type == 'fee':
            payment = get_object_or_404(FeePayment, pk=payment_id)
            student = payment.fee.student
            
            # Check permission
            if not (request.user.is_staff or 
                   (hasattr(request.user, 'student') and request.user.student == student)):
                return HttpResponse('Permission denied', status=403)
            
            payment_data = {
                'receipt_number': payment.receipt_number,
                'amount': payment.amount,
                'payment_date': payment.payment_date,
                'payment_method': payment.get_payment_mode_display(),
                'description': f"{payment.fee.category.get_name_display()} - Term {payment.fee.term}"
            }
            
        else:  # bill
            payment = get_object_or_404(BillPayment, pk=payment_id)
            student = payment.bill.student
            
            if not (request.user.is_staff or 
                   (hasattr(request.user, 'student') and request.user.student == student)):
                return HttpResponse('Permission denied', status=403)
            
            payment_data = {
                'receipt_number': payment.reference_number,
                'amount': payment.amount,
                'payment_date': payment.payment_date,
                'payment_method': payment.get_payment_mode_display(),
                'description': f"Bill #{payment.bill.bill_number}"
            }
        
        student_data = {
            'student_id': student.student_id,
            'full_name': student.get_full_name(),
            'class_level': student.get_class_level_display()
        }
        
        # Generate receipt
        receipt_generator = ProfessionalReceiptGenerator(
            school_name=settings.SCHOOL_INFO['NAME'],
            school_address=settings.SCHOOL_INFO.get('ADDRESS', ''),
            school_logo_path=settings.SCHOOL_INFO.get('LOGO_PATH')
        )
        
        filename = f"receipt_{payment_data['receipt_number']}.pdf"
        return receipt_generator.generate_receipt_response(payment_data, student_data, filename)


class ContactSupportView(TemplateView):
    """Simple contact support page"""
    template_name = 'payment/contact_support.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'school_name': settings.SCHOOL_INFO.get('NAME', 'School Management System'),
            'contact_email': settings.SCHOOL_INFO.get('EMAIL', 'support@school.edu'),
            'contact_phone': settings.SCHOOL_INFO.get('PHONE', '+233 XXX XXX XXXX')
        })
        return context


class OutstandingFeesAPIView(LoginRequiredMixin, View):
    """API endpoint for outstanding fees"""
    
    def get(self, request):
        try:
            # Get current user's outstanding fees
            if hasattr(request.user, 'student'):
                student = request.user.student
                
                # Query outstanding fees
                outstanding_fees = Fee.objects.filter(
                    student=student,
                    status__in=['unpaid', 'partial']
                ).select_related('category').order_by('due_date')
                
                # Format response
                fees_data = []
                for fee in outstanding_fees:
                    fees_data.append({
                        'id': fee.id,
                        'category': fee.category.get_name_display(),
                        'category_display': fee.category.get_name_display(),
                        'term': fee.term,
                        'academic_year': fee.academic_year,
                        'amount': float(fee.amount),
                        'paid': float(fee.paid_amount),
                        'balance': float(fee.balance),
                        'description': f"{fee.category.get_name_display()} - Term {fee.term}",
                        'due_date': fee.due_date.strftime('%Y-%m-%d'),
                        'status': fee.get_status_display(),
                        'status_code': fee.status,
                        'is_overdue': fee.due_date < timezone.now().date() and fee.balance > 0
                    })
                
                return JsonResponse({
                    'success': True,
                    'fees': fees_data,
                    'total_outstanding': sum(fee.balance for fee in outstanding_fees),
                    'count': len(fees_data)
                })
            else:
                return JsonResponse({
                    'success': True,
                    'fees': [],
                    'total_outstanding': 0,
                    'count': 0,
                    'message': 'No student profile found'
                })
                
        except Exception as e:
            logger.error(f"Outstanding fees API error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Unable to fetch outstanding fees',
                'message': str(e)
            }, status=500)
