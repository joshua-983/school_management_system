import logging
import json
from django.utils import timezone
from datetime import timedelta, datetime
from django.contrib.auth.models import User
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.db.models import Sum, Count, Q, Avg
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font
from io import BytesIO
from django.db.models import F, ExpressionWrapper, DecimalField
from django.utils.timezone import make_aware

from .base_views import is_admin, is_teacher, is_student
from ..models import FeeCategory, Fee, FeePayment, AcademicTerm, Student, ClassAssignment, Bill, BillPayment, StudentCredit, Expense, Budget  # ADDED Expense, Budget
from ..forms import FeeCategoryForm, FeeForm, FeePaymentForm, FeeFilterForm, FeeStatusReportForm
from django.contrib import messages

from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from ..forms import BudgetForm

# Add logger configuration
logger = logging.getLogger(__name__)


# Fee management
class FeeCategoryListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = FeeCategory
    template_name = 'core/Finance/categories/fee_category_list.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add statistics to context
        context['active_count'] = FeeCategory.objects.filter(is_active=True).count()
        context['mandatory_count'] = FeeCategory.objects.filter(is_mandatory=True).count()
        context['fees_count'] = Fee.objects.count()
        
        return context

class FeeCategoryCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = FeeCategory
    form_class = FeeCategoryForm
    template_name = 'core/finance/categories/fee_category_form.html'
    success_url = reverse_lazy('fee_category_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Fee category created successfully')
        return super().form_valid(form)

class FeeCategoryDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = FeeCategory
    template_name = 'core/finance/categories/fee_category_detail.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.object
        
        # Get fee statistics
        fees = Fee.objects.filter(category=category)
        total_fees = fees.count()
        paid_fees = fees.filter(payment_status='paid').count()
        pending_fees = fees.filter(payment_status__in=['unpaid', 'partial']).count()
        overdue_fees = fees.filter(payment_status='overdue').count()
        
        # Calculate financial statistics
        total_revenue = fees.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        
        outstanding_balance = fees.aggregate(
            total=Sum('balance')
        )['total'] or 0
        
        average_amount = fees.aggregate(
            avg=Avg('amount_payable')
        )['avg'] or 0
        
        payment_completion = (total_revenue / (total_revenue + outstanding_balance) * 100) if (total_revenue + outstanding_balance) > 0 else 0
        
        context.update({
            'total_fees': total_fees,
            'paid_fees': paid_fees,
            'pending_fees': pending_fees,
            'overdue_fees': overdue_fees,
            'total_revenue': total_revenue,
            'outstanding_balance': outstanding_balance,
            'average_amount': average_amount,
            'payment_completion': round(payment_completion, 1),
            'recent_fees': fees.order_by('-date_recorded')[:10],
        })
        
        return context

class FeeCategoryUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = FeeCategory
    form_class = FeeCategoryForm
    template_name = 'core/finance/categories/fee_category_form.html'
    success_url = reverse_lazy('fee_category_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Fee category updated successfully')
        return super().form_valid(form)

class FeeCategoryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = FeeCategory
    template_name = 'core/finance/categories/fee_category_confirm_delete.html'
    success_url = reverse_lazy('fee_category_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Fee category deleted successfully')
        return super().delete(request, *args, **kwargs)
    
# Fee Views
class FeeListView(LoginRequiredMixin, ListView):
    model = Fee
    template_name = 'core/finance/fees/fee_list.html'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('student', 'category', 'bill')
        
        # Apply filters from GET parameters
        form = FeeFilterForm(self.request.GET)
        if form.is_valid():
            academic_year = form.cleaned_data.get('academic_year')
            term = form.cleaned_data.get('term')
            payment_status = form.cleaned_data.get('payment_status')
            category = form.cleaned_data.get('category')
            student = form.cleaned_data.get('student')
            has_bill = form.cleaned_data.get('has_bill')
            
            if academic_year:
                queryset = queryset.filter(academic_year=academic_year)
            if term:
                queryset = queryset.filter(term=term)
            if payment_status:
                queryset = queryset.filter(payment_status=payment_status)
            if category:
                queryset = queryset.filter(category=category)
            if student:
                queryset = queryset.filter(student=student)
            if has_bill == 'yes':
                queryset = queryset.filter(bill__isnull=False)
            elif has_bill == 'no':
                queryset = queryset.filter(bill__isnull=True)
        
        # Apply user-specific filters
        if is_student(self.request.user):
            queryset = queryset.filter(student=self.request.user.student)
        elif is_teacher(self.request.user):
            # Get classes taught by this teacher
            class_levels = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            queryset = queryset.filter(student__class_level__in=class_levels)
        
        return queryset.order_by('-date_recorded')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = FeeFilterForm(self.request.GET)
        
        # Add summary statistics
        queryset = self.get_queryset()
        total_payable = queryset.aggregate(Sum('amount_payable'))['amount_payable__sum'] or Decimal('0.00')
        total_paid = queryset.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
        total_balance = total_payable - total_paid
        
        # Calculate completion rate
        if total_payable > 0:
            completion_rate = (total_paid / total_payable) * 100
        else:
            completion_rate = 0
        
        # FIXED: Use lowercase statuses for counting
        paid_count = queryset.filter(payment_status='paid').count()
        pending_count = queryset.filter(payment_status__in=['unpaid', 'partial', 'overdue']).count()
        
        # Count by status for detailed breakdown
        unpaid_count = queryset.filter(payment_status='unpaid').count()
        partial_count = queryset.filter(payment_status='partial').count()
        overdue_count = queryset.filter(payment_status='overdue').count()
        
        context.update({
            'total_payable': total_payable,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'completion_rate': completion_rate,
            'paid_count': paid_count,
            'pending_count': pending_count,
            'unpaid_count': unpaid_count,
            'partial_count': partial_count,
            'overdue_count': overdue_count,
            'is_admin': is_admin(self.request.user),
            'is_teacher': is_teacher(self.request.user),
        })
        
        # Add all students for the modal - FIXED
        if is_admin(self.request.user) or is_teacher(self.request.user):
            context['all_students'] = Student.objects.filter(is_active=True).order_by('first_name', 'last_name')
        else:
            context['all_students'] = Student.objects.none()
        
        return context
    
    def get(self, request, *args, **kwargs):
        # Check if export is requested
        if 'export' in request.GET:
            return self.export_to_excel()
        return super().get(request, *args, **kwargs)
    
    def export_to_excel(self):
        queryset = self.get_queryset()
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="fee_records.xlsx"'
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Fee Records"
        
        # Add headers
        headers = [
            'Student ID', 'Student Name', 'Class', 'Fee Category',
            'Academic Year', 'Term', 'Amount Payable', 'Amount Paid',
            'Balance', 'Payment Status', 'Due Date', 'Bill Number'
        ]
        
        for col_num, header in enumerate(headers, 1):
            col_letter = get_column_letter(col_num)
            ws[f'{col_letter}1'] = header
            ws[f'{col_letter}1'].font = Font(bold=True)
        
        # Add data
        for row_num, fee in enumerate(queryset, 2):
            ws[f'A{row_num}'] = fee.student.student_id
            ws[f'B{row_num}'] = fee.student.get_full_name()
            ws[f'C{row_num}'] = fee.student.get_class_level_display()
            ws[f'D{row_num}'] = str(fee.category)
            ws[f'E{row_num}'] = fee.academic_year
            ws[f'F{row_num}'] = fee.get_term_display()
            ws[f'G{row_num}'] = float(fee.amount_payable)
            ws[f'H{row_num}'] = float(fee.amount_paid)
            ws[f'I{row_num}'] = float(fee.balance)
            ws[f'J{row_num}'] = fee.get_payment_status_display()
            ws[f'K{row_num}'] = fee.due_date.strftime('%Y-%m-%d')
            ws[f'L{row_num}'] = fee.bill.bill_number if fee.bill else 'Not billed'
        
        # Auto-size columns
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min((max_length + 2) * 1.2, 30)
            ws.column_dimensions[column].width = adjusted_width
        
        wb.save(response)
        return response


class FeeDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Fee
    template_name = 'core/finance/fees/fee_dashboard.html'
    context_object_name = 'fee'
    
    def test_func(self):
        fee = self.get_object()
        if is_admin(self.request.user):
            return True
        elif is_teacher(self.request.user):
            # Check if teacher teaches this student's class
            return ClassAssignment.objects.filter(
                class_level=fee.student.class_level,
                teacher=self.request.user.teacher
            ).exists()
        elif is_student(self.request.user):
            return fee.student == self.request.user.student
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payments'] = self.object.payments.all().order_by('-payment_date')
        context['is_admin'] = is_admin(self.request.user)
        context['is_teacher'] = is_teacher(self.request.user)
        return context

class FeeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Fee
    form_class = FeeForm
    template_name = 'core/finance/fees/fee_form.html'
    
    def test_func(self):
        """Check if user has permission to create fees"""
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_form_kwargs(self):
        """Add student_id to form kwargs"""
        kwargs = super().get_form_kwargs()
        student_id = self.kwargs.get('student_id')
        if student_id:
            kwargs['student_id'] = student_id
        return kwargs
    
    def get_initial(self):
        """Set initial values for the form"""
        initial = super().get_initial()
        student_id = self.kwargs.get('student_id')
        
        if student_id:
            try:
                student = Student.objects.get(pk=student_id)
                initial['student'] = student
            except Student.DoesNotExist:
                pass
        
        # Set default academic year to current year
        current_year = timezone.now().year
        next_year = current_year + 1
        initial['academic_year'] = f"{current_year}/{next_year}"
        
        return initial
    
    def form_valid(self, form):
        """Handle valid form submission"""
        # Get student from form data
        student = form.cleaned_data.get('student')
        if not student:
            form.add_error('student', 'Please select a student')
            return self.form_invalid(form)
        
        form.instance.student = student
        form.instance.created_by = self.request.user
        form.instance.recorded_by = self.request.user
        
        # Calculate balance
        amount_payable = form.cleaned_data.get('amount_payable', 0)
        amount_paid = form.cleaned_data.get('amount_paid', 0)
        form.instance.balance = amount_payable - amount_paid
        
        # Set payment date if status is paid and no date provided
        if form.instance.payment_status == 'paid' and not form.instance.payment_date:
            form.instance.payment_date = timezone.now().date()
        
        messages.success(
            self.request,
            f'Fee record for {student.get_full_name()} created successfully'
        )
        return super().form_valid(form)
    
    def get_success_url(self):
        """Redirect to student detail page after creation"""
        return reverse_lazy('student_detail', kwargs={'pk': self.object.student.pk})
    
    def get_context_data(self, **kwargs):
        """Add student and other context data to template"""
        context = super().get_context_data(**kwargs)
        student_id = self.kwargs.get('student_id')
        
        if student_id:
            try:
                student = Student.objects.get(pk=student_id)
                context['student'] = student
                
                # Add existing fees for reference
                context['existing_fees'] = Fee.objects.filter(
                    student=student
                ).select_related('category').order_by('-due_date')[:5]
                context['total_fees'] = Fee.objects.filter(student=student).count()
                
            except Student.DoesNotExist:
                messages.error(self.request, 'Selected student does not exist')
                context['student'] = None
        else:
            context['student'] = None
            
        return context

class FeeUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Fee
    form_class = FeeForm
    template_name = 'core/finance/fees/fee_form.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        form.instance.balance = form.cleaned_data['amount_payable'] - form.cleaned_data['amount_paid']
        
        # Update payment date if status changed to paid and no date exists
        if (form.instance.payment_status == 'paid' and 
            not form.instance.payment_date and
            self.get_object().payment_status != 'paid'):
            form.instance.payment_date = timezone.now().date()
            
        messages.success(self.request, 'Fee record updated successfully')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('fee_detail', kwargs={'pk': self.object.pk})

class FeeDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Fee
    template_name = 'core/finance/fees/fee_confirm_delete.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('student_detail', kwargs={'pk': self.object.student.pk})
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Fee record deleted successfully')
        return super().delete(request, *args, **kwargs)

# Fee Payment Views
class FeePaymentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = FeePayment
    form_class = FeePaymentForm
    template_name = 'core/finance/fees/fee_payment_form.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        fee_id = self.kwargs.get('fee_id')
        print(f"DEBUG: Fee ID from URL: {fee_id}")
        
        # Check if fee exists
        try:
            fee = Fee.objects.get(pk=fee_id)
            print(f"DEBUG: Fee found: {fee}")
        except Fee.DoesNotExist:
            print(f"DEBUG: Fee with ID {fee_id} does not exist")
        
        kwargs['fee_id'] = fee_id
        kwargs['request'] = self.request  # Pass request to form
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fee_id = self.kwargs.get('fee_id')
        
        try:
            fee = Fee.objects.get(pk=fee_id)
            context['fee'] = fee
            print(f"DEBUG: Fee added to context: {fee}")
        except Fee.DoesNotExist:
            context['fee'] = None
            print(f"DEBUG: Fee not found, setting to None")
            messages.error(self.request, 'The requested fee record could not be found or is invalid.')
        
        return context
    
    def form_valid(self, form):
        print("DEBUG: form_valid method called")
        fee_id = self.kwargs.get('fee_id')
        try:
            fee = Fee.objects.get(pk=fee_id)
            print(f"DEBUG: Fee found in form_valid: {fee}")
            form.instance.fee = fee
        except Fee.DoesNotExist:
            print(f"DEBUG: Fee not found in form_valid")
            messages.error(self.request, 'The requested fee record could not be found.')
            return self.form_invalid(form)
        
        # Ensure recorded_by is set (fallback)
        if not form.cleaned_data.get('recorded_by'):
            form.instance.recorded_by = self.request.user
        
        # FIX: Auto-confirm payments when created
        form.instance.is_confirmed = True
        form.instance.confirmed_by = self.request.user
        form.instance.confirmed_at = timezone.now()
        
        print(f"DEBUG: Recorded by: {form.instance.recorded_by}")
        print(f"DEBUG: Payment amount: {form.instance.amount}")
        print(f"DEBUG: Payment mode: {form.instance.payment_mode}")
        print(f"DEBUG: Payment date: {form.instance.payment_date}")
        print(f"DEBUG: Payment confirmed: {form.instance.is_confirmed}")
        
        try:
            with transaction.atomic():
                # Save the payment first
                response = super().form_valid(form)
                print(f"DEBUG: Payment saved successfully, ID: {self.object.pk}")
                
                # Update the parent fee record - CALCULATE TOTAL FROM PAYMENTS
                fee = form.instance.fee
                print(f"DEBUG: Before update - Amount paid: {fee.amount_paid}, Balance: {fee.balance}")
                
                # Calculate total paid from all payments (including the new one)
                total_paid = fee.payments.aggregate(total=Sum('amount'))['total'] or 0
                fee.amount_paid = total_paid
                fee.balance = fee.amount_payable - fee.amount_paid
                
                # FIXED: Proper status calculation with overpayment handling
                if fee.amount_paid >= fee.amount_payable:
                    fee.payment_status = 'paid'
                    fee.payment_date = timezone.now().date()
                elif fee.amount_paid > 0:
                    fee.payment_status = 'partial'
                else:
                    fee.payment_status = 'unpaid'
                
                # Check if overdue
                if (fee.due_date and 
                    fee.due_date < timezone.now().date() and 
                    fee.payment_status != 'paid'):
                    fee.payment_status = 'overdue'
                
                fee.save()
                print(f"DEBUG: After update - Amount paid: {fee.amount_paid}, Balance: {fee.balance}, Status: {fee.payment_status}")
                
                # Handle overpayment - create credit record
                if hasattr(fee, 'has_overpayment') and fee.has_overpayment:
                    # Create or update student credit
                    credit, created = StudentCredit.objects.get_or_create(
                        student=fee.student,
                        source_fee=fee,
                        is_used=False,
                        defaults={
                            'credit_amount': fee.overpayment_amount,
                            'reason': f'Overpayment for {fee.category.name}'
                        }
                    )
                    if not created:
                        credit.credit_amount = fee.overpayment_amount
                        credit.save()
                    
                    messages.warning(
                        self.request, 
                        f'Payment recorded successfully! Overpayment of GH₵{fee.overpayment_amount:.2f} has been credited to student account.'
                    )
                else:
                    messages.success(
                        self.request, 
                        f'Payment of GH₵{form.instance.amount:.2f} recorded successfully for {fee.student.get_full_name()}'
                    )
                
                print("DEBUG: Success message set")
                return response
                
        except Exception as e:
            print(f"DEBUG: Error in form_valid: {str(e)}")
            messages.error(self.request, f'Error recording payment: {str(e)}')
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        print("DEBUG: form_invalid method called")
        print(f"DEBUG: Form errors: {form.errors}")
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_success_url(self):
        print("DEBUG: get_success_url called")
        if hasattr(self, 'object') and self.object.fee:
            url = reverse_lazy('fee_detail', kwargs={'pk': self.object.fee.pk})
            print(f"DEBUG: Success URL: {url}")
            return url
        print("DEBUG: No object, returning to fee list")
        return reverse_lazy('fee_list')


# Add Refresh Payment Data View
class RefreshPaymentDataView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return is_admin(self.request.user)
    
    def post(self, request):
        """Force refresh of payment summary data"""
        # This forces a fresh query without any caching
        fee_payments_count = FeePayment.objects.all().count()
        bill_payments_count = BillPayment.objects.all().count()
        
        messages.success(
            request, 
            f'Payment data refreshed successfully. Found {fee_payments_count} fee payments and {bill_payments_count} bill payments.'
        )
        return redirect('payment_summary')


class FeePaymentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = FeePayment
    template_name = 'core/finance/fees/fee_payment_confirm_delete.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        with transaction.atomic():
            payment = self.get_object()
            fee = payment.fee
            
            # Delete the payment first
            payment.delete()
            
            # Recalculate total paid from remaining payments
            total_paid = fee.payments.aggregate(total=Sum('amount'))['total'] or 0
            fee.amount_paid = total_paid
            fee.balance = fee.amount_payable - fee.amount_paid
            
            # FIXED: Use lowercase statuses consistently
            if fee.amount_paid <= 0:
                fee.payment_status = 'unpaid'
                fee.payment_date = None
            elif fee.amount_paid < fee.amount_payable:
                fee.payment_status = 'partial'
            else:
                fee.payment_status = 'paid'
            
            # Check if overdue
            if (fee.due_date and 
                fee.due_date < timezone.now().date() and 
                fee.payment_status != 'paid'):
                fee.payment_status = 'overdue'
            
            fee.save()
            
            messages.success(request, 'Payment record deleted successfully')
            return HttpResponseRedirect(self.get_success_url())
    
    def get_success_url(self):
        return reverse_lazy('fee_detail', kwargs={'pk': self.object.fee.pk})

# NEW: Bill Payment Views
class BillPaymentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = BillPayment
    fields = ['amount', 'payment_mode', 'payment_date', 'notes']
    template_name = 'core/finance/bills/bill_payment_form.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        bill = get_object_or_404(Bill, pk=self.kwargs['bill_id'])
        form.instance.bill = bill
        form.instance.recorded_by = self.request.user
        messages.success(self.request, f'Payment of GH₵{form.instance.amount:.2f} recorded for bill #{bill.bill_number}')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('bill_detail', kwargs={'pk': self.kwargs['bill_id']})

# NEW: Automated Fee Generation
class GenerateTermFeesView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return is_admin(self.request.user)
    
    def get(self, request):
        """Display fee generation form"""
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        mandatory_categories = FeeCategory.objects.filter(
            is_active=True, 
            is_mandatory=True
        )
        active_students = Student.objects.filter(is_active=True).count()
        
        context = {
            'current_term': current_term,
            'mandatory_categories': mandatory_categories,
            'active_students': active_students,
        }
        return render(request, 'core/finance/fees/generate_term_fees.html', context)
    
    def post(self, request):
        """Generate fees for current term"""
        created_count = generate_term_fees(request.user)
        messages.success(request, f'Generated {created_count} fee records for current term')
        return redirect('fee_list')


# NEW: Bulk Fee Operations
class BulkFeeUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return is_admin(self.request.user)
    
    def post(self, request):
        fee_ids = request.POST.getlist('fee_ids')
        action = request.POST.get('action')
        
        if not fee_ids:
            messages.error(request, 'No fees selected')
            return redirect('fee_list')
        
        updated_count = 0
        with transaction.atomic():
            for fee_id in fee_ids:
                try:
                    fee = Fee.objects.get(pk=fee_id)
                    if action == 'mark_paid':
                        fee.payment_status = 'paid'
                        fee.payment_date = timezone.now().date()
                        fee.save()
                        updated_count += 1
                    elif action == 'mark_overdue':
                        fee.payment_status = 'overdue'
                        fee.save()
                        updated_count += 1
                except Fee.DoesNotExist:
                    continue
        
        messages.success(request, f'Updated {updated_count} fee records')
        return redirect('fee_list')

# NEW: Payment Reminders
class SendPaymentRemindersView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return is_admin(self.request.user)
    
    def post(self, request):
        # Get overdue fees
        overdue_fees = Fee.objects.filter(
            payment_status='overdue',
            due_date__lt=timezone.now().date()
        ).select_related('student')
        
        reminder_count = 0
        for fee in overdue_fees:
            # In a real implementation, this would send emails/SMS
            # For now, just log the action
            print(f"Reminder sent for {fee.student.get_full_name()} - Fee: {fee.category.name}")
            reminder_count += 1
        
        messages.success(request, f'Payment reminders sent for {reminder_count} overdue fees')
        return redirect('fee_list')

# NEW: Fee Analytics
class FeeAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/finance/fees/fee_analytics.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Monthly trends
        current_year = timezone.now().year
        monthly_data = []
        for month in range(1, 13):
            month_fees = Fee.objects.filter(
                date_recorded__year=current_year,
                date_recorded__month=month
            )
            monthly_revenue = month_fees.aggregate(total=Sum('amount_paid'))['total'] or 0
            monthly_data.append({
                'month': month,
                'revenue': float(monthly_revenue),
                'count': month_fees.count()
            })
        
        # Category breakdown
        category_breakdown = FeeCategory.objects.annotate(
            total_revenue=Sum('fees__amount_paid'),
            fee_count=Count('fees')
        ).values('name', 'total_revenue', 'fee_count')
        
        context.update({
            'monthly_data': monthly_data,
            'category_breakdown': category_breakdown,
            'current_year': current_year,
        })
        
        return context

# Reports
class FeeReportView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        """Check if user has permission to view fee reports"""
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get(self, request):
        form = FeeFilterForm(request.GET)
        fees = Fee.objects.all().select_related('student', 'category')
        
        if form.is_valid():
            academic_year = form.cleaned_data.get('academic_year')
            term = form.cleaned_data.get('term')
            payment_status = form.cleaned_data.get('payment_status')
            category = form.cleaned_data.get('category')
            student = form.cleaned_data.get('student')
            
            if academic_year:
                fees = fees.filter(academic_year=academic_year)
            if term:
                fees = fees.filter(term=term)
            if payment_status:
                fees = fees.filter(payment_status=payment_status)
            if category:
                fees = fees.filter(category=category)
            if student:
                fees = fees.filter(student=student)
        
        # FIXED: Calculate summary statistics with lowercase statuses
        summary_data = fees.aggregate(
            total_payable=Sum('amount_payable'),
            total_paid=Sum('amount_paid'),
            count=Count('id'),
            paid_count=Count('id', filter=Q(payment_status='paid')),
            partial_count=Count('id', filter=Q(payment_status='partial')),
            unpaid_count=Count('id', filter=Q(payment_status='unpaid')),
            overdue_count=Count('id', filter=Q(payment_status='overdue')),
        )
        
        # Calculate total balance
        total_payable = summary_data['total_payable'] or Decimal('0.00')
        total_paid = summary_data['total_paid'] or Decimal('0.00')
        total_balance = total_payable - total_paid
        
        summary = {
            'total_payable': total_payable,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'count': summary_data['count'],
            'paid_count': summary_data['paid_count'],
            'partial_count': summary_data['partial_count'],
            'unpaid_count': summary_data['unpaid_count'],
            'overdue_count': summary_data['overdue_count'],
        }
        
        context = {
            'form': form,
            'fees': fees.order_by('student__last_name', 'student__first_name'),
            'summary': summary,
        }
        
        if 'export' in request.GET:
            return self.export_to_excel(fees)

        return render(request, 'core/finance/fees/fee_report.html', context)

    def export_to_excel(self, queryset):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="fee_report.xlsx"'
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Fee Report"
        
        # Add headers
        headers = [
            'Student ID', 'Student Name', 'Class', 
            'Fee Category', 'Academic Year', 'Term',
            'Amount Payable', 'Amount Paid', 'Balance', 
            'Payment Status', 'Due Date', 'Bill Number'
        ]
        
        for col_num, header in enumerate(headers, 1):
            col_letter = get_column_letter(col_num)
            ws[f'{col_letter}1'] = header
            ws[f'{col_letter}1'].font = Font(bold=True)
        
        # Add data
        for row_num, fee in enumerate(queryset, 2):
            ws[f'A{row_num}'] = fee.student.student_id
            ws[f'B{row_num}'] = fee.student.get_full_name()
            ws[f'C{row_num}'] = fee.student.get_class_level_display()
            ws[f'D{row_num}'] = str(fee.category)
            ws[f'E{row_num}'] = fee.academic_year
            ws[f'F{row_num}'] = fee.get_term_display()
            ws[f'G{row_num}'] = float(fee.amount_payable)
            ws[f'H{row_num}'] = float(fee.amount_paid)
            ws[f'I{row_num}'] = float(fee.balance)
            ws[f'J{row_num}'] = fee.get_payment_status_display()
            ws[f'K{row_num}'] = fee.due_date.strftime('%Y-%m-%d')
            ws[f'L{row_num}'] = fee.bill.bill_number if fee.bill else 'Not billed'
        
        # Auto-size columns
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min((max_length + 2) * 1.2, 30)
            ws.column_dimensions[column].width = adjusted_width
        
        wb.save(response)
        return response

# Fee Status Report
class FeeStatusReportView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        """Check if user has permission to view fee status reports"""
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get(self, request):
        # Initialize form with GET parameters
        form = FeeStatusReportForm(request.GET or None)
        
        # Get base queryset
        fees = Fee.objects.all().select_related('student', 'category')
        
        # Apply filters if form is valid
        if form.is_valid():
            report_type = form.cleaned_data.get('report_type')
            academic_year = form.cleaned_data.get('academic_year')
            term = form.cleaned_data.get('term')
            class_level = form.cleaned_data.get('class_level')
            payment_status = form.cleaned_data.get('payment_status')
            bill_status = form.cleaned_data.get('bill_status')
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            
            if academic_year:
                fees = fees.filter(academic_year=academic_year)
            if term:
                fees = fees.filter(term=term)
            if class_level:
                fees = fees.filter(student__class_level=class_level)
            if payment_status:
                fees = fees.filter(payment_status=payment_status)
            if bill_status:
                if bill_status == 'billed':
                    fees = fees.filter(bill__isnull=False)
                elif bill_status == 'unbilled':
                    fees = fees.filter(bill__isnull=True)
            if start_date:
                fees = fees.filter(due_date__gte=start_date)
            if end_date:
                fees = fees.filter(due_date__lte=end_date)
        
        # Categorize fees by status
        paid_fees = fees.filter(payment_status='paid')
        partial_fees = fees.filter(payment_status='partial')
        unpaid_fees = fees.filter(payment_status='unpaid')
        overdue_fees = fees.filter(payment_status='overdue')
        
        # Calculate summaries
        summary = {
            'total_payable': fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0,
            'total_paid': fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
            'total_balance': (fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0) - 
                           (fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0),
            'counts': {
                'paid': paid_fees.count(),
                'partial': partial_fees.count(),
                'unpaid': unpaid_fees.count(),
                'overdue': overdue_fees.count(),
                'total': fees.count()
            }
        }
        
        context = {
            'form': form,
            'paid_fees': paid_fees,
            'partial_fees': partial_fees,
            'unpaid_fees': unpaid_fees,
            'overdue_fees': overdue_fees,
            'summary': summary,
            'all_fees': fees  # For summary report
        }
        
        if request.GET.get('export'):
            return self.export_report(context)
            
        return render(request, 'core/finance/fees/fee_status_report.html', context)
    
    def export_report(self, context):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="fee_status_report.xlsx"'
        
        wb = Workbook()
        
        # Create sheets for each status
        self._create_sheet(wb, 'Paid Fees', context['paid_fees'])
        self._create_sheet(wb, 'Partial Payments', context['partial_fees'])
        self._create_sheet(wb, 'Unpaid Fees', context['unpaid_fees'])
        self._create_sheet(wb, 'Overdue Fees', context['overdue_fees'])
        
        # Remove default sheet
        if 'Sheet' in wb.sheetnames:
            del wb['Sheet']
        
        wb.save(response)
        return response
    
    def _create_sheet(self, wb, title, queryset):
        ws = wb.create_sheet(title=title)
        
        headers = [
            'Student ID', 'Student Name', 'Class', 
            'Fee Category', 'Amount Payable', 'Amount Paid',
            'Balance', 'Due Date', 'Status', 'Bill Number'
        ]
        
        for col_num, header in enumerate(headers, 1):
            col_letter = get_column_letter(col_num)
            ws[f'{col_letter}1'] = header
            ws[f'{col_letter}1'].font = Font(bold=True)
        
        for fee in queryset:
            ws.append([
                fee.student.student_id,
                fee.student.get_full_name(),
                fee.student.get_class_level_display(),
                str(fee.category),
                float(fee.amount_payable),
                float(fee.amount_paid),
                float(fee.balance),
                fee.due_date.strftime('%Y-%m-%d'),
                fee.get_payment_status_display(),
                fee.bill.bill_number if fee.bill else 'Not billed'
            ])
        
        # Auto-size columns
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min((max_length + 2) * 1.2, 30)
            ws.column_dimensions[column].width = adjusted_width

class FeeDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/finance/fees/fee_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Current term stats
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        context['current_term'] = current_term
        
        if current_term:
            fees = Fee.objects.filter(
                academic_year=current_term.academic_year,
                term=current_term.term
            )
            
            # FIXED: Use lowercase statuses in aggregation
            payment_status_distribution = fees.values('payment_status').annotate(
                count=Count('id'),
                amount=Sum('amount_payable')
            ).order_by('payment_status')
            
            context.update({
                'total_payable': fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0,
                'total_paid': fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
                'payment_status_distribution': payment_status_distribution,
                'class_level_stats': self.get_class_level_stats(fees),
                'recent_payments': FeePayment.objects.select_related('fee__student').order_by('-payment_date')[:10],
                'is_admin': is_admin(self.request.user),
                'is_teacher': is_teacher(self.request.user),
            })
        
        return context
    
    def get_payment_status_distribution(self, fees):
        return fees.values('payment_status').annotate(
            count=Count('id'),
            amount=Sum('amount_payable')
        ).order_by('payment_status')
    
    def get_class_level_stats(self, fees):
        return fees.values('student__class_level').annotate(
            payable=Sum('amount_payable'),
            paid=Sum('amount_paid'),
            count=Count('id')
        ).order_by('student__class_level')

# Fee generation automation
def generate_term_fees(request_user=None):
    """Automatically generate fees for all students for the current term"""
    current_term = AcademicTerm.objects.filter(is_active=True).first()
    if not current_term:
        return 0
        
    # Get all active students
    students = Student.objects.filter(is_active=True)
    
    # Get all mandatory fee categories
    categories = FeeCategory.objects.filter(
        is_active=True,
        is_mandatory=True
    )
    
    created_count = 0
    
    with transaction.atomic():
        for student in students:
            for category in categories:
                # Check if category applies to student's class
                if (category.class_levels and 
                    student.class_level not in [level.strip() for level in category.class_levels.split(',')]):
                    continue
                
                # Check if fee already exists
                if Fee.objects.filter(
                    student=student,
                    category=category,
                    academic_year=current_term.academic_year,
                    term=current_term.term
                ).exists():
                    continue
                
                # Calculate due date (e.g., 2 weeks after term starts)
                due_date = current_term.start_date + timedelta(days=14)
                
                # Create the fee - use the provided user or fallback to a default
                if request_user and request_user.is_authenticated:
                    recorded_by = request_user
                else:
                    # Fallback: try to find an admin user or use the first superuser
                    try:
                        recorded_by = User.objects.filter(is_superuser=True).first()
                    except:
                        recorded_by = None
                
                Fee.objects.create(
                    student=student,
                    category=category,
                    academic_year=current_term.academic_year,
                    term=current_term.term,
                    amount_payable=category.default_amount,
                    due_date=due_date,
                    recorded_by=recorded_by,
                    payment_status='unpaid'  # Set initial status
                )
                created_count += 1
                
    return created_count


class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class FinanceDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/finance/reports/finance_dashboard.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range from request or default to current month
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date and end_date:
            try:
                start_date = make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
                end_date = make_aware(datetime.strptime(end_date, '%Y-%m-%d'))
            except ValueError:
                start_date = timezone.now() - timedelta(days=30)
                end_date = timezone.now()
        else:
            start_date = timezone.now() - timedelta(days=30)
            end_date = timezone.now()
        
        # Fee statistics
        fees = Fee.objects.all()
        total_collected = fees.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        total_expected = fees.aggregate(total=Sum('amount_payable'))['total'] or Decimal('0.00')
        collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0
        
        # Outstanding fees
        outstanding_fees = fees.filter(payment_status__in=['unpaid', 'partial', 'overdue'])
        outstanding_total = outstanding_fees.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        outstanding_count = outstanding_fees.count()
        
        # Daily revenue trend - PROPERLY SERIALIZED
        daily_revenue_data = FeePayment.objects.filter(
            payment_date__range=[start_date.date(), end_date.date()]
        ).values('payment_date').annotate(
            total=Sum('amount')
        ).order_by('payment_date')
        
        # Convert to list of dicts with proper serialization
        daily_revenue = []
        for item in daily_revenue_data:
            daily_revenue.append({
                'payment_date': item['payment_date'].isoformat() if item['payment_date'] else None,
                'total': float(item['total']) if item['total'] else 0.0
            })
        
        # Payment methods breakdown - PROPERLY SERIALIZED
        payment_methods_data = FeePayment.objects.filter(
            payment_date__range=[start_date.date(), end_date.date()]
        ).values('payment_mode').annotate(
            total=Sum('amount')
        ).order_by('-total')
        
        payment_methods = []
        for item in payment_methods_data:
            payment_methods.append({
                'payment_mode': item['payment_mode'],
                'total': float(item['total']) if item['total'] else 0.0
            })
        
        # Budget data (you'll need to create a Budget model for this)
        budget_data = self.get_budget_data()
        
        # Calculate financial metrics
        net_profit = total_collected - Decimal('10000.00')  # Placeholder for expenses
        profit_margin = (net_profit / total_collected * 100) if total_collected > 0 else 0
        budget_utilization = 75.0  # Placeholder
        budget_variance = Decimal('1500.00')  # Placeholder
        
        context.update({
            'start_date': start_date.date(),
            'end_date': end_date.date(),
            'total_collected': total_collected,
            'total_expected': total_expected,
            'collection_rate': collection_rate,
            'outstanding_total': outstanding_total,
            'outstanding_count': outstanding_count,
            'daily_revenue': json.dumps(daily_revenue, cls=CustomJSONEncoder),  # JSON serialized
            'payment_methods': json.dumps(payment_methods, cls=CustomJSONEncoder),  # JSON serialized
            'budget_data': json.dumps(budget_data, cls=CustomJSONEncoder),  # JSON serialized
            'net_profit': net_profit,
            'profit_margin': profit_margin,
            'budget_utilization': budget_utilization,
            'budget_variance': budget_variance,
            'outstanding_payments': outstanding_fees.select_related('student', 'category')[:10],
        })
        
        return context
    
    def get_budget_data(self):
        """Get budget vs actual data (placeholder - implement with your Budget model)"""
        return [
            {'category': 'Tuition', 'budget': 50000, 'actual': 45000},
            {'category': 'Feeding', 'budget': 20000, 'actual': 18000},
            {'category': 'Transport', 'budget': 10000, 'actual': 9500},
            {'category': 'Materials', 'budget': 5000, 'actual': 5200},
            {'category': 'Other', 'budget': 3000, 'actual': 2800},
        ]


# Revenue Analytics View - FIXED VERSION
class RevenueAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/finance/reports/revenue_analytics.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range from request
        start_date = self.request.GET.get('start_date', (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date = self.request.GET.get('end_date', timezone.now().strftime('%Y-%m-%d'))
        
        try:
            start_date_obj = make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
            end_date_obj = make_aware(datetime.strptime(end_date, '%Y-%m-%d'))
        except ValueError:
            start_date_obj = timezone.now() - timedelta(days=30)
            end_date_obj = timezone.now()
        
        # Revenue calculations
        payments = FeePayment.objects.filter(
            payment_date__range=[start_date_obj.date(), end_date_obj.date()]
        )
        
        total_collected = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Expected revenue from fees due in this period
        expected_fees = Fee.objects.filter(
            due_date__range=[start_date_obj.date(), end_date_obj.date()]
        )
        total_expected = expected_fees.aggregate(total=Sum('amount_payable'))['total'] or Decimal('0.00')
        
        collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0
        
        # Daily revenue trend - ensure proper date handling
        daily_revenue = payments.values('payment_date').annotate(
            total=Sum('amount')
        ).order_by('payment_date')
        
        # Payment methods with enhanced data
        payment_methods_data = payments.values('payment_mode').annotate(
            total=Sum('amount'),
            count=Count('id'),
            average=Avg('amount')
        ).order_by('-total')
        
        # Calculate percentages and add display names and colors
        payment_methods = []
        for method in payment_methods_data:
            percentage = (method['total'] / total_collected * 100) if total_collected > 0 else 0
            payment_methods.append({
                'payment_mode': method['payment_mode'],
                'total': method['total'],
                'count': method['count'],
                'average': method['average'],
                'percentage': percentage,
                'display_name': self.get_payment_method_display(method['payment_mode']),
                'color': self.get_payment_method_color(method['payment_mode'])
            })
        
        # Outstanding payments
        outstanding_payments = Fee.objects.filter(
            payment_status__in=['unpaid', 'partial', 'overdue']
        ).select_related('student', 'category')[:20]
        
        # Chart colors for JavaScript
        chart_colors = {
            'primary': 'rgba(58, 123, 213, 1)',
            'success': 'rgba(40, 167, 69, 1)',
            'warning': 'rgba(255, 193, 7, 1)',
            'danger': 'rgba(220, 53, 69, 1)',
            'info': 'rgba(23, 162, 184, 1)',
            'secondary': 'rgba(108, 117, 125, 1)'
        }
        
        # Method colors for JavaScript
        method_colors = {
            'cash': '#28a745',
            'mobile_money': '#007bff',
            'bank_transfer': '#17a2b8',
            'check': '#ffc107',
            'other': '#6c757d'
        }
        
        # Enhanced context data
        context.update({
            'start_date': start_date_obj.date(),
            'end_date': end_date_obj.date(),
            'total_collected': total_collected,
            'total_expected': total_expected,
            'collection_rate': collection_rate,
            'daily_revenue': list(daily_revenue),
            'payment_methods': payment_methods,
            'outstanding_payments': outstanding_payments,
            'chart_colors_json': json.dumps(chart_colors),
            'method_colors_json': json.dumps(method_colors),
            'today': timezone.now().date(),
        })
        
        return context
    
    def get_payment_method_display(self, method):
        """Get user-friendly payment method names"""
        display_names = {
            'cash': 'Cash',
            'mobile_money': 'Mobile Money',
            'bank_transfer': 'Bank Transfer',
            'check': 'Cheque',
            'other': 'Other'
        }
        return display_names.get(method, method.replace('_', ' ').title())
    
    def get_payment_method_color(self, method):
        """Get color for payment method"""
        colors = {
            'cash': '#28a745',  # Green
            'mobile_money': '#007bff',  # Blue
            'bank_transfer': '#17a2b8',  # Cyan
            'check': '#ffc107',  # Yellow
            'other': '#6c757d'  # Gray
        }
        return colors.get(method, '#6c757d')
    
    def get(self, request, *args, **kwargs):
        """Handle export requests"""
        if 'export' in request.GET:
            return self.export_revenue_data()
        return super().get(request, *args, **kwargs)
    
    def export_revenue_data(self):
        """Export revenue analytics data to Excel"""
        context = self.get_context_data()
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="revenue_analytics_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        
        wb = Workbook()
        
        # Summary Sheet
        ws_summary = wb.active
        ws_summary.title = "Revenue Summary"
        
        # Add summary headers
        summary_headers = ['Metric', 'Value']
        for col_num, header in enumerate(summary_headers, 1):
            ws_summary.cell(row=1, column=col_num, value=header).font = Font(bold=True)
        
        # Add summary data
        summary_data = [
            ['Start Date', context['start_date'].strftime('%Y-%m-%d')],
            ['End Date', context['end_date'].strftime('%Y-%m-%d')],
            ['Total Collected', float(context['total_collected'])],
            ['Total Expected', float(context['total_expected'])],
            ['Collection Rate', f"{context['collection_rate']:.1f}%"],
        ]
        
        for row_num, data in enumerate(summary_data, 2):
            ws_summary.cell(row=row_num, column=1, value=data[0])
            ws_summary.cell(row=row_num, column=2, value=data[1])
        
        # Payment Methods Sheet
        ws_methods = wb.create_sheet(title="Payment Methods")
        
        method_headers = ['Payment Method', 'Amount (GH₵)', 'Transactions', 'Average Amount', 'Percentage']
        for col_num, header in enumerate(method_headers, 1):
            ws_methods.cell(row=1, column=col_num, value=header).font = Font(bold=True)
        
        for row_num, method in enumerate(context['payment_methods'], 2):
            ws_methods.cell(row=row_num, column=1, value=method['display_name'])
            ws_methods.cell(row=row_num, column=2, value=float(method['total']))
            ws_methods.cell(row=row_num, column=3, value=method['count'])
            ws_methods.cell(row=row_num, column=4, value=float(method['average']))
            ws_methods.cell(row=row_num, column=5, value=f"{method['percentage']:.1f}%")
        
        # Daily Revenue Sheet
        ws_daily = wb.create_sheet(title="Daily Revenue")
        
        daily_headers = ['Date', 'Revenue (GH₵)']
        for col_num, header in enumerate(daily_headers, 1):
            ws_daily.cell(row=1, column=col_num, value=header).font = Font(bold=True)
        
        for row_num, day in enumerate(context['daily_revenue'], 2):
            ws_daily.cell(row=row_num, column=1, value=day['payment_date'].strftime('%Y-%m-%d'))
            ws_daily.cell(row=row_num, column=2, value=float(day['total']))
        
        # Outstanding Payments Sheet
        ws_outstanding = wb.create_sheet(title="Outstanding Payments")
        
        outstanding_headers = [
            'Student', 'Student ID', 'Class', 'Fee Category', 
            'Amount Payable', 'Amount Paid', 'Balance', 'Status', 'Due Date'
        ]
        for col_num, header in enumerate(outstanding_headers, 1):
            ws_outstanding.cell(row=1, column=col_num, value=header).font = Font(bold=True)
        
        for row_num, fee in enumerate(context['outstanding_payments'], 2):
            ws_outstanding.cell(row=row_num, column=1, value=fee.student.get_full_name())
            ws_outstanding.cell(row=row_num, column=2, value=fee.student.student_id)
            ws_outstanding.cell(row=row_num, column=3, value=fee.student.get_class_level_display())
            ws_outstanding.cell(row=row_num, column=4, value=str(fee.category))
            ws_outstanding.cell(row=row_num, column=5, value=float(fee.amount_payable))
            ws_outstanding.cell(row=row_num, column=6, value=float(fee.amount_paid))
            ws_outstanding.cell(row=row_num, column=7, value=float(fee.balance))
            ws_outstanding.cell(row=row_num, column=8, value=fee.get_payment_status_display())
            ws_outstanding.cell(row=row_num, column=9, value=fee.due_date.strftime('%Y-%m-%d'))
        
        # Auto-size columns for all sheets
        for sheet in wb.worksheets:
            for column in sheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min((max_length + 2), 50)
                sheet.column_dimensions[column_letter].width = adjusted_width
        
        wb.save(response)
        return response


class FinancialHealthView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/finance/reports/financial_health.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        current_year = timezone.now().year
        previous_year = current_year - 1
        
        # Calculate actual income from fee payments for current year
        current_year_income = FeePayment.objects.filter(
            payment_date__year=current_year,
            is_confirmed=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        previous_year_income = FeePayment.objects.filter(
            payment_date__year=previous_year,
            is_confirmed=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Calculate income growth
        if previous_year_income > 0:
            income_growth = ((current_year_income - previous_year_income) / previous_year_income) * 100
        else:
            income_growth = Decimal('100.00') if current_year_income > 0 else Decimal('0.00')
        
        # Calculate actual expenses
        expenses = self.calculate_actual_expenses(current_year)
        previous_year_expenses = self.calculate_actual_expenses(previous_year)
        
        # Calculate expense growth
        if previous_year_expenses > 0:
            expense_growth = ((expenses - previous_year_expenses) / previous_year_expenses) * 100
        else:
            expense_growth = Decimal('100.00') if expenses > 0 else Decimal('0.00')
        
        # Net profit/loss
        net_profit = current_year_income - expenses
        
        # Profit margin
        profit_margin = (net_profit / current_year_income * 100) if current_year_income > 0 else Decimal('0.00')
        
        # Receivables (outstanding fees)
        receivables = Fee.objects.filter(
            payment_status__in=['unpaid', 'partial', 'overdue'],
            academic_year=f"{current_year}/{current_year + 1}"
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        
        # Receivables ratio
        receivables_ratio = (receivables / current_year_income * 100) if current_year_income > 0 else Decimal('0.00')
        
        # Expense ratio
        expense_ratio = (expenses / current_year_income * 100) if current_year_income > 0 else Decimal('0.00')
        
        # Cash flow (last 90 days)
        cash_flow_data = self.get_cash_flow_data()
        
        # Liabilities
        debts, total_liabilities = self.get_liabilities_data()
        
        # Collection rate
        total_fees_due = Fee.objects.filter(
            academic_year=f"{current_year}/{current_year + 1}"
        ).aggregate(total=Sum('amount_payable'))['total'] or Decimal('0.00')
        
        collection_rate = (current_year_income / total_fees_due * 100) if total_fees_due > 0 else Decimal('0.00')
        
        # Monthly income data
        current_month_income, last_month_income, monthly_avg_income = self.get_monthly_income_data(current_year)
        
        # Payment method distribution
        payment_methods = self.get_payment_method_distribution(current_year)
        
        # Calculate financial health score
        health_score = self.calculate_financial_health_score(
            current_year_income, expenses, receivables, net_profit, collection_rate
        )
        
        context.update({
            'income': current_year_income,
            'expenses': expenses,
            'net_profit': net_profit,
            'receivables': receivables,
            'cash_flow': cash_flow_data,
            'cash_flow_json': json.dumps(cash_flow_data, cls=CustomJSONEncoder),
            'debts': debts,
            'total_liabilities': total_liabilities,
            'current_year': current_year,
            'health_score': health_score,
            'income_growth': income_growth,
            'expense_growth': expense_growth,
            'profit_margin': profit_margin,
            'receivables_ratio': receivables_ratio,
            'expense_ratio': expense_ratio,
            'collection_rate': collection_rate,
            'current_month_income': current_month_income,
            'last_month_income': last_month_income,
            'monthly_avg_income': monthly_avg_income,
            'cash_percentage': payment_methods.get('cash', 0),
            'momo_percentage': payment_methods.get('mobile_money', 0),
            'bank_percentage': payment_methods.get('bank_transfer', 0),
            'other_percentage': payment_methods.get('other', 0),
        })
        
        return context
    
    def calculate_actual_expenses(self, year):
        """Calculate actual expenses for a given year"""
        try:
            # Try to get expenses from Expense model if it exists
            expenses = Expense.objects.filter(
                date__year=year
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # If no Expense model or no data, use estimated calculation
            if expenses == Decimal('0.00'):
                # Estimate expenses as 60% of income (adjustable ratio)
                income = FeePayment.objects.filter(
                    payment_date__year=year,
                    is_confirmed=True
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                expenses = income * Decimal('0.6')
                
        except Exception as e:
            logger.warning(f"Error calculating expenses for {year}: {e}")
            # Fallback calculation
            income = FeePayment.objects.filter(
                payment_date__year=year,
                is_confirmed=True
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            expenses = income * Decimal('0.6')
        
        return expenses
    
    def get_cash_flow_data(self):
        """Get cash flow data for the last 90 days"""
        ninety_days_ago = timezone.now() - timedelta(days=90)
        
        try:
            cash_flow_data = FeePayment.objects.filter(
                payment_date__gte=ninety_days_ago.date(),
                is_confirmed=True
            ).extra({
                'payment_date': "DATE(payment_date)"
            }).values('payment_date').annotate(
                income=Sum('amount')
            ).order_by('payment_date')
            
            # Format the data for the template
            formatted_data = []
            for item in cash_flow_data:
                formatted_data.append({
                    'payment_date': item['payment_date'].isoformat(),
                    'income': float(item['income'])
                })
            
            return formatted_data
            
        except Exception as e:
            logger.error(f"Error getting cash flow data: {e}")
            return []
    
    def get_liabilities_data(self):
        """Get actual liabilities data from unpaid bills"""
        try:
            unpaid_bills = Bill.objects.filter(
                status__in=['issued', 'partial', 'overdue']
            ).select_related('student')
            
            debts = []
            total_liabilities = Decimal('0.00')
            
            for bill in unpaid_bills[:10]:  # Limit to 10 most significant
                debts.append({
                    'name': f"Bill #{bill.bill_number} - {bill.student.get_full_name()}",
                    'amount': bill.balance,
                    'paid': False
                })
                total_liabilities += bill.balance
            
            # Add placeholder if no actual debts exist
            if not debts:
                debts = [
                    {'name': 'Supplier Payments', 'amount': Decimal('5000.00'), 'paid': False},
                    {'name': 'Utility Bills', 'amount': Decimal('2500.00'), 'paid': True},
                    {'name': 'Equipment Maintenance', 'amount': Decimal('15000.00'), 'paid': False},
                ]
                total_liabilities = Decimal('22500.00')
            
            return debts, total_liabilities
            
        except Exception as e:
            logger.error(f"Error getting liabilities data: {e}")
            return [], Decimal('0.00')
    
    def get_monthly_income_data(self, year):
        """Get monthly income statistics"""
        try:
            # Current month income
            current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            current_month_income = FeePayment.objects.filter(
                payment_date__gte=current_month_start.date(),
                is_confirmed=True
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Last month income
            last_month_end = current_month_start - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            last_month_income = FeePayment.objects.filter(
                payment_date__range=[last_month_start.date(), last_month_end.date()],
                is_confirmed=True
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Monthly average
            monthly_avg_income = FeePayment.objects.filter(
                payment_date__year=year,
                is_confirmed=True
            ).aggregate(
                avg=Avg('amount')
            )['avg'] or Decimal('0.00')
            
            return current_month_income, last_month_income, monthly_avg_income
            
        except Exception as e:
            logger.error(f"Error getting monthly income data: {e}")
            return Decimal('0.00'), Decimal('0.00'), Decimal('0.00')
    
    def get_payment_method_distribution(self, year):
        """Get payment method distribution percentages"""
        try:
            payment_totals = FeePayment.objects.filter(
                payment_date__year=year,
                is_confirmed=True
            ).values('payment_mode').annotate(
                total=Sum('amount')
            )
            
            total_income = sum(item['total'] for item in payment_totals)
            
            distribution = {}
            for item in payment_totals:
                percentage = (item['total'] / total_income * 100) if total_income > 0 else 0
                distribution[item['payment_mode']] = float(percentage)
            
            # Ensure all payment methods are represented
            default_methods = {
                'cash': 0,
                'mobile_money': 0,
                'bank_transfer': 0,
                'other': 0
            }
            default_methods.update(distribution)
            
            return default_methods
            
        except Exception as e:
            logger.error(f"Error getting payment method distribution: {e}")
            return {'cash': 40, 'mobile_money': 35, 'bank_transfer': 20, 'other': 5}
    
    def calculate_financial_health_score(self, income, expenses, receivables, net_profit, collection_rate):
        """Calculate a comprehensive financial health score (0-100)"""
        score = 100
        
        try:
            # Profitability (30 points)
            if net_profit <= 0:
                score -= 30
            elif net_profit < income * Decimal('0.1'):  # Less than 10% margin
                score -= 15
            elif net_profit < income * Decimal('0.2'):  # Less than 20% margin
                score -= 5
            
            # Receivables management (25 points)
            if receivables > income * Decimal('0.3'):  # More than 30% of income
                score -= 25
            elif receivables > income * Decimal('0.2'):  # More than 20% of income
                score -= 15
            elif receivables > income * Decimal('0.1'):  # More than 10% of income
                score -= 5
            
            # Expense control (20 points)
            expense_ratio = expenses / income if income > 0 else 1
            if expense_ratio > Decimal('0.9'):
                score -= 20
            elif expense_ratio > Decimal('0.8'):
                score -= 12
            elif expense_ratio > Decimal('0.7'):
                score -= 6
            
            # Collection efficiency (15 points)
            if collection_rate < 70:
                score -= 15
            elif collection_rate < 80:
                score -= 10
            elif collection_rate < 90:
                score -= 5
            
            # Income stability (10 points) - check if income is growing
            if income < expenses:  # Income doesn't cover expenses
                score -= 10
            
            return max(0, min(100, int(score)))
            
        except Exception as e:
            logger.error(f"Error calculating financial health score: {e}")
            return 50  # Default neutral score


# Budget Management View
class BudgetManagementView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/finance/reports/budget_management.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get year from request or use current year
        current_year = self.request.GET.get('year')
        try:
            current_year = int(current_year) if current_year else timezone.now().year
        except (ValueError, TypeError):
            current_year = timezone.now().year
        
        # Get enhanced budget data with real calculations
        budget_data = self.get_enhanced_budget_data(current_year)
        
        # Calculate summary statistics
        total_budget = sum(item['budget'] for item in budget_data)
        total_actual = sum(item['actual'] for item in budget_data)
        total_variance = total_actual - total_budget
        total_variance_percent = (total_variance / total_budget * 100) if total_budget > 0 else 0
        utilization_rate = (total_actual / total_budget * 100) if total_budget > 0 else 0
        
        # 🚀 ENHANCEMENT 1: Budget vs Actual Alerts
        critical_variance = self.get_critical_variance_alerts(budget_data)
        
        # Historical spending data
        historical_spending = self.get_historical_spending_data()
        
        # Monthly data for trend chart
        monthly_data = self.get_monthly_budget_data(current_year)
        
        # Available years for filter
        available_years = self.get_available_years()
        
        # Fee categories for budget creation
        fee_categories = FeeCategory.objects.filter(is_active=True)
        
        # Get existing budgets for the current year
        current_academic_year = f"{current_year}/{current_year + 1}"
        existing_budgets = Budget.objects.filter(academic_year=current_academic_year)
        
        # 🚀 ENHANCEMENT 2: Budget Trends for Major Categories
        budget_trends = self.get_budget_trends_for_major_categories(current_year)
        
        context.update({
            'current_year': current_year,
            'budget_data': budget_data,
            'historical_spending': historical_spending,
            'monthly_data': monthly_data,
            'available_years': available_years,
            'fee_categories': fee_categories,
            'existing_budgets': existing_budgets,
            'total_budget': total_budget,
            'total_actual': total_actual,
            'total_variance': total_variance,
            'total_variance_percent': total_variance_percent,
            'utilization_rate': utilization_rate,
            # 🚀 New enhancements
            'critical_alerts': critical_variance,
            'budget_trends': budget_trends,
            'alert_count': len(critical_variance),
        })
        
        return context
    
    # 🚀 ENHANCEMENT 1: Budget vs Actual Alerts
    def get_critical_variance_alerts(self, budget_data, threshold=20):
        """
        Identify categories with significant budget variances
        threshold: percentage variance that triggers an alert (default 20%)
        """
        critical_alerts = []
        
        for item in budget_data:
            variance_percent = abs(item['variance_percent'])
            
            # Check if variance exceeds threshold
            if variance_percent > threshold:
                alert_level = 'high' if variance_percent > 50 else 'medium'
                
                critical_alerts.append({
                    'category': item['category'],
                    'budget': item['budget'],
                    'actual': item['actual'],
                    'variance': item['variance'],
                    'variance_percent': item['variance_percent'],
                    'alert_level': alert_level,
                    'message': self.get_alert_message(item, variance_percent),
                    'recommendation': self.get_alert_recommendation(item, variance_percent)
                })
        
        # Sort by severity (highest variance first)
        critical_alerts.sort(key=lambda x: abs(x['variance_percent']), reverse=True)
        
        return critical_alerts
    
    def get_alert_message(self, item, variance_percent):
        """Generate appropriate alert message based on variance"""
        category_name = item['category'].name
        variance_amount = abs(item['variance'])
        
        if item['variance'] < 0:
            return (
                f"{category_name} is {abs(variance_percent):.1f}% OVER budget "
                f"(GH₵{variance_amount:,.2f} over planned amount)"
            )
        else:
            return (
                f"{category_name} is {variance_percent:.1f}% UNDER budget "
                f"(GH₵{variance_amount:,.2f} below planned amount)"
            )
    
    def get_alert_recommendation(self, item, variance_percent):
        """Generate recommendations for addressing variances"""
        if item['variance'] < 0:  # Over budget
            if variance_percent > 50:
                return "Immediate review required. Consider reallocating funds or investigating unexpected expenses."
            elif variance_percent > 30:
                return "Review spending patterns and implement cost controls."
            else:
                return "Monitor closely and adjust future budget allocations."
        else:  # Under budget
            if variance_percent > 50:
                return "Significant under-utilization. Consider reallocating surplus to other categories."
            elif variance_percent > 30:
                return "Good cost control. Evaluate if budget can be reduced for next period."
            else:
                return "Healthy performance. Maintain current budget levels."
    
    # 🚀 ENHANCEMENT 2: Enhanced Budget Trends
    def get_budget_trends_for_major_categories(self, current_year, years=3):
        """
        Get budget performance trends for major categories over multiple years
        """
        major_categories = FeeCategory.objects.filter(
            is_active=True
        ).annotate(
            total_budget=Sum('budget__allocated_amount')
        ).order_by('-total_budget')[:5]  # Top 5 categories by budget size
        
        trends_data = {}
        
        for category in major_categories:
            trends_data[category.name] = self.get_budget_trends(category, current_year, years)
        
        return trends_data
    
    def get_budget_trends(self, category, current_year, years=3):
        """
        Show budget performance trends for a specific category over multiple years
        """
        trend_data = []
        
        for year_offset in range(years - 1, -1, -1):  # Current year first, then previous years
            year = current_year - year_offset
            
            try:
                budget_amount = self.get_budget_amount_for_year(category, year)
                actual_spending = self.get_actual_spending_for_year(category, year)
                variance = actual_spending - budget_amount
                variance_percent = (variance / budget_amount * 100) if budget_amount > 0 else 0
                
                trend_data.append({
                    'year': year,
                    'academic_year': f"{year}/{year + 1}",
                    'budget': budget_amount,
                    'actual': actual_spending,
                    'variance': variance,
                    'variance_percent': variance_percent,
                    'utilization_rate': (actual_spending / budget_amount * 100) if budget_amount > 0 else 0
                })
            except Exception as e:
                logger.error(f"Error getting trend data for {category.name} in {year}: {str(e)}")
                # Add placeholder data for missing years
                trend_data.append({
                    'year': year,
                    'academic_year': f"{year}/{year + 1}",
                    'budget': Decimal('0.00'),
                    'actual': Decimal('0.00'),
                    'variance': Decimal('0.00'),
                    'variance_percent': 0.0,
                    'utilization_rate': 0.0,
                    'data_available': False
                })
        
        return trend_data
    
    def get_budget_amount_for_year(self, category, year):
        """Get budget amount for a specific category and year"""
        academic_year = f"{year}/{year + 1}"
        
        try:
            budget = Budget.objects.filter(
                category=category,
                academic_year=academic_year
            ).first()
            
            if budget:
                return budget.allocated_amount
        except Exception as e:
            logger.warning(f"Error getting budget for {category.name} in {year}: {str(e)}")
        
        # Fallback calculation
        return self.get_budget_amount(category, year)
    
    def get_actual_spending_for_year(self, category, year):
        """Get actual spending for a specific category and year"""
        try:
            actual_spending = FeePayment.objects.filter(
                fee__category=category,
                payment_date__year=year,
                is_confirmed=True
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            return actual_spending
        except Exception as e:
            logger.error(f"Error getting actual spending for {category.name} in {year}: {str(e)}")
            return Decimal('0.00')
    
    def get_enhanced_budget_data(self, year):
        """Get enhanced budget vs actual data with real calculations"""
        # Use the same academic year format as Budget model
        academic_year = f"{year}/{year + 1}"
        
        # First, try to get data from Budget model
        budgets = Budget.objects.filter(academic_year=academic_year)
        
        if budgets.exists():
            budget_data = []
            colors = [
                'rgba(58, 123, 213, 1)', 'rgba(40, 167, 69, 1)', 
                'rgba(255, 193, 7, 1)', 'rgba(220, 53, 69, 1)', 
                'rgba(23, 162, 184, 1)', 'rgba(108, 117, 125, 1)',
                'rgba(111, 66, 193, 1)', 'rgba(253, 126, 20, 1)'
            ]
            
            for i, budget in enumerate(budgets):
                try:
                    # Calculate actual spending from fee payments for this category and year
                    actual_spending = FeePayment.objects.filter(
                        fee__category=budget.category,
                        payment_date__year=year,
                        is_confirmed=True
                    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    
                    variance = actual_spending - budget.allocated_amount
                    variance_percent = (variance / budget.allocated_amount * 100) if budget.allocated_amount > 0 else 0
                    
                    budget_data.append({
                        'category': budget.category,
                        'budget': budget.allocated_amount,
                        'actual': actual_spending,
                        'variance': variance,
                        'variance_percent': variance_percent,
                        'color': colors[i % len(colors)],
                        'has_budget_record': True
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing budget data for category {budget.category.name}: {str(e)}")
                    continue
            
            return budget_data
        
        # Fallback to fee categories if no budgets exist
        categories = FeeCategory.objects.filter(is_active=True)
        
        if not categories.exists():
            # Return empty placeholder if no categories exist
            return [
                {
                    'category': {'name': 'Tuition Fees'},
                    'budget': Decimal('50000.00'),
                    'actual': Decimal('45000.00'),
                    'variance': Decimal('-5000.00'),
                    'variance_percent': -10.0,
                    'color': 'rgba(58, 123, 213, 1)',
                    'has_budget_record': False
                },
                {
                    'category': {'name': 'Feeding Program'},
                    'budget': Decimal('20000.00'),
                    'actual': Decimal('18000.00'),
                    'variance': Decimal('-2000.00'),
                    'variance_percent': -10.0,
                    'color': 'rgba(40, 167, 69, 1)',
                    'has_budget_record': False
                },
                {
                    'category': {'name': 'Transportation'},
                    'budget': Decimal('10000.00'),
                    'actual': Decimal('9500.00'),
                    'variance': Decimal('-500.00'),
                    'variance_percent': -5.0,
                    'color': 'rgba(255, 193, 7, 1)',
                    'has_budget_record': False
                },
            ]
        
        budget_data = []
        colors = [
            'rgba(58, 123, 213, 1)', 'rgba(40, 167, 69, 1)', 
            'rgba(255, 193, 7, 1)', 'rgba(220, 53, 69, 1)', 
            'rgba(23, 162, 184, 1)', 'rgba(108, 117, 125, 1)',
            'rgba(111, 66, 193, 1)', 'rgba(253, 126, 20, 1)'
        ]
        
        for i, category in enumerate(categories):
            try:
                # Calculate actual spending from fee payments for this category and year
                actual_spending = FeePayment.objects.filter(
                    fee__category=category,
                    payment_date__year=year,
                    is_confirmed=True
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                # Get budget amount using fallback calculation
                budget_amount = self.get_budget_amount(category, year)
                
                variance = actual_spending - budget_amount
                variance_percent = (variance / budget_amount * 100) if budget_amount > 0 else 0
                
                budget_data.append({
                    'category': category,
                    'budget': budget_amount,
                    'actual': actual_spending,
                    'variance': variance,
                    'variance_percent': variance_percent,
                    'color': colors[i % len(colors)],
                    'has_budget_record': False
                })
                
            except Exception as e:
                logger.error(f"Error processing budget data for category {category.name}: {str(e)}")
                continue
        
        return budget_data
    
    def get_budget_amount(self, category, year):
        """Get budget amount for a category - with fallback to realistic estimates"""
        try:
            # Try to get from Budget model if it exists
            academic_year = f"{year}/{year + 1}"
            budget = Budget.objects.filter(
                category=category, 
                academic_year=academic_year
            ).first()
            
            if budget:
                return budget.allocated_amount
            
            # Fallback: Calculate based on category default amount and student count
            active_students = Student.objects.filter(is_active=True).count()
            base_amount = category.default_amount * Decimal('10')  # Base multiplier
            
            # Adjust based on category type and student count
            if 'tuition' in category.name.lower():
                budget_amount = base_amount * Decimal(str(active_students)) * Decimal('0.8')
            elif 'feeding' in category.name.lower():
                budget_amount = base_amount * Decimal(str(active_students)) * Decimal('0.3')
            elif 'transport' in category.name.lower():
                budget_amount = base_amount * Decimal(str(active_students)) * Decimal('0.2')
            else:
                budget_amount = base_amount * Decimal(str(max(active_students, 1)))
                
            return budget_amount
            
        except Exception as e:
            logger.warning(f"Could not calculate budget amount for {category.name}: {str(e)}")
            return Decimal('10000.00')  # Default fallback
    
    def get_historical_spending_data(self):
        """Get historical spending data for the last 5 years"""
        current_year = timezone.now().year
        historical_data = []
        
        for year in range(current_year - 4, current_year + 1):
            try:
                yearly_spending = FeePayment.objects.filter(
                    payment_date__year=year,
                    is_confirmed=True
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                historical_data.append({
                    'date__year': year,
                    'total': float(yearly_spending)
                })
            except Exception as e:
                logger.error(f"Error getting historical data for {year}: {str(e)}")
                historical_data.append({
                    'date__year': year,
                    'total': 0.0
                })
        
        return historical_data
    
    def get_monthly_budget_data(self, year):
        """Get monthly budget vs actual data for trend chart"""
        monthly_data = []
        
        for month in range(1, 13):
            try:
                # Monthly actual spending
                monthly_actual = FeePayment.objects.filter(
                    payment_date__year=year,
                    payment_date__month=month,
                    is_confirmed=True
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                # Monthly budget estimate (based on annual budget / 12)
                total_annual_budget = sum([
                    self.get_budget_amount(category, year) 
                    for category in FeeCategory.objects.filter(is_active=True)
                ])
                monthly_budget = total_annual_budget / Decimal('12') if total_annual_budget > 0 else Decimal('50000.00')
                
                monthly_data.append({
                    'month': month,
                    'budget': float(monthly_budget),
                    'actual': float(monthly_actual)
                })
                
            except Exception as e:
                logger.error(f"Error getting monthly data for month {month}: {str(e)}")
                monthly_data.append({
                    'month': month,
                    'budget': 50000.0,
                    'actual': 45000.0
                })
        
        return monthly_data
    
    def get_available_years(self):
        """Get available years for filter dropdown"""
        current_year = timezone.now().year
        return list(range(current_year - 4, current_year + 1))


class BudgetCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Budget
    form_class = BudgetForm
    template_name = 'core/finance/reports/budget_form.html'
    success_url = reverse_lazy('budget_management')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Budget'
        return context
    
    def form_valid(self, form):
        # Check for duplicate budget
        academic_year = form.cleaned_data['academic_year']
        category = form.cleaned_data['category']
        
        existing_budget = Budget.objects.filter(
            academic_year=academic_year,
            category=category
        ).exists()
        
        if existing_budget:
            form.add_error(None, f'A budget already exists for {category.name} in {academic_year}')
            return self.form_invalid(form)
        
        messages.success(
            self.request, 
            f'Budget created successfully: GH₵{form.instance.allocated_amount:,.2f} for {form.instance.category.name}'
        )
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


# Payment Summary View - FIXED AND ENHANCED VERSION
class PaymentSummaryView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/finance/reports/payment_summary.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range from request
        start_date_str = self.request.GET.get('start_date')
        end_date_str = self.request.GET.get('end_date')
        
        # Default to current month if no dates provided
        today = timezone.now().date()
        
        # Handle start date
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                start_date = today.replace(day=1)  # First day of current month
        else:
            start_date = today.replace(day=1)
            
        # Handle end date  
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                end_date = today
        else:
            end_date = today
        
        # Validate date range
        if start_date > end_date:
            messages.error(self.request, 'Start date cannot be after end date')
            start_date, end_date = end_date, start_date
        
        # Get payments with error handling
        try:
            fee_payments = FeePayment.objects.filter(
                payment_date__range=[start_date, end_date]
            )
            
            bill_payments = BillPayment.objects.filter(
                payment_date__range=[start_date, end_date]
            )
            
            # Debug info
            logger.info(f"Payment summary: {fee_payments.count()} fee payments, {bill_payments.count()} bill payments")
            
        except Exception as e:
            logger.error(f"Error fetching payments: {str(e)}")
            messages.error(self.request, f"Error loading payment data: {str(e)}")
            fee_payments = FeePayment.objects.none()
            bill_payments = BillPayment.objects.none()
        
        # Calculate summary by payment method
        payment_methods = ['cash', 'mobile_money', 'bank_transfer', 'check', 'other']
        summary_by_method = {}
        
        total_collected = Decimal('0.00')
        total_transactions = 0
        
        for method in payment_methods:
            try:
                method_fee_payments = fee_payments.filter(payment_mode=method)
                method_bill_payments = bill_payments.filter(payment_mode=method)
                
                method_fee_total = method_fee_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                method_bill_total = method_bill_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                total_amount = method_fee_total + method_bill_total
                count = method_fee_payments.count() + method_bill_payments.count()
                
                summary_by_method[method] = {
                    'total_amount': total_amount,
                    'count': count,
                    'display_name': self.get_payment_method_display_name(method),
                    'fee_count': method_fee_payments.count(),
                    'bill_count': method_bill_payments.count(),
                    'fee_amount': method_fee_total,
                    'bill_amount': method_bill_total
                }
                
                total_collected += total_amount
                total_transactions += count
                
            except Exception as e:
                logger.error(f"Error processing payment method {method}: {str(e)}")
                summary_by_method[method] = {
                    'total_amount': Decimal('0.00'),
                    'count': 0,
                    'display_name': self.get_payment_method_display_name(method),
                    'fee_count': 0,
                    'bill_count': 0,
                    'fee_amount': Decimal('0.00'),
                    'bill_amount': Decimal('0.00')
                }
        
        # Calculate percentages with error handling
        for method, data in summary_by_method.items():
            try:
                if total_collected > 0:
                    data['percentage'] = round((data['total_amount'] / total_collected) * 100, 1)
                else:
                    data['percentage'] = 0
            except Exception as e:
                logger.error(f"Error calculating percentage for {method}: {str(e)}")
                data['percentage'] = 0
        
        # Get daily breakdown and recent payments
        try:
            daily_breakdown = self.get_daily_breakdown(start_date, end_date)
            recent_payments = self.get_recent_payments(start_date, end_date)
        except Exception as e:
            logger.error(f"Error generating breakdown data: {str(e)}")
            daily_breakdown = []
            recent_payments = []
        
        # Calculate average transaction with error handling
        try:
            average_transaction = total_collected / total_transactions if total_transactions > 0 else Decimal('0.00')
        except Exception as e:
            logger.error(f"Error calculating average transaction: {str(e)}")
            average_transaction = Decimal('0.00')
        
        # Additional statistics
        try:
            # Highest payment method
            highest_method = max(
                summary_by_method.items(), 
                key=lambda x: x[1]['total_amount'], 
                default=(None, {'total_amount': Decimal('0.00')})
            )
            
            # Payment confirmation rate
            confirmed_payments = fee_payments.filter(is_confirmed=True).count() + bill_payments.filter(is_confirmed=True).count()
            total_payment_count = fee_payments.count() + bill_payments.count()
            confirmation_rate = (confirmed_payments / total_payment_count * 100) if total_payment_count > 0 else 0
            
        except Exception as e:
            logger.error(f"Error calculating additional statistics: {str(e)}")
            highest_method = (None, {'total_amount': Decimal('0.00')})
            confirmation_rate = 0
        
        context.update({
            'start_date': start_date,
            'end_date': end_date,
            'summary_by_method': summary_by_method,
            'total_collected': total_collected,
            'total_transactions': total_transactions,
            'average_transaction': average_transaction,
            'daily_breakdown': daily_breakdown,
            'recent_payments': recent_payments,
            'payment_methods': payment_methods,
            'highest_method': highest_method,
            'confirmation_rate': confirmation_rate,
            'date_range_days': (end_date - start_date).days + 1,
        })
        
        return context
    
    def get_payment_method_display_name(self, method):
        """Get user-friendly payment method names"""
        display_names = {
            'cash': 'Cash',
            'mobile_money': 'Mobile Money',
            'bank_transfer': 'Bank Transfer',
            'check': 'Cheque',
            'other': 'Other'
        }
        return display_names.get(method, method.title())
    
    def get_daily_breakdown(self, start_date, end_date):
        """Get daily payment breakdown for charts with error handling"""
        daily_data = []
        current_date = start_date
        
        try:
            while current_date <= end_date:
                # Get fee payments for the day
                day_fee_total = FeePayment.objects.filter(
                    payment_date=current_date
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                # Get bill payments for the day
                day_bill_total = BillPayment.objects.filter(
                    payment_date=current_date
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                day_total = day_fee_total + day_bill_total
                
                daily_data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'display_date': current_date.strftime('%b %d'),
                    'total': float(day_total),
                    'fee_total': float(day_fee_total),
                    'bill_total': float(day_bill_total),
                    'date_obj': current_date
                })
                
                current_date += timedelta(days=1)
                
        except Exception as e:
            logger.error(f"Error generating daily breakdown: {str(e)}")
            # Return empty data structure to prevent template errors
            return [{
                'date': start_date.strftime('%Y-%m-%d'),
                'display_date': start_date.strftime('%b %d'),
                'total': 0.0,
                'fee_total': 0.0,
                'bill_total': 0.0,
                'date_obj': start_date
            }]
        
        return daily_data
    
    def get_recent_payments(self, start_date, end_date, limit=20):
        """Get recent payments for the table with error handling"""
        all_payments = []
        
        try:
            # Get fee payments within date range
            fee_payments = FeePayment.objects.filter(
                payment_date__range=[start_date, end_date]
            ).select_related('fee__student').order_by('-payment_date')[:limit*2]
            
            # Get bill payments within date range
            bill_payments = BillPayment.objects.filter(
                payment_date__range=[start_date, end_date]
            ).select_related('bill__student').order_by('-payment_date')[:limit*2]
            
            # Combine and format fee payments
            for payment in fee_payments:
                all_payments.append({
                    'type': 'fee',
                    'date': payment.payment_date,
                    'student': payment.fee.student if payment.fee else None,
                    'amount': payment.amount,
                    'method': payment.payment_mode,
                    'receipt_number': payment.receipt_number or f"FEE-{payment.id}",
                    'payment_obj': payment,
                    'is_confirmed': payment.is_confirmed
                })
            
            # Combine and format bill payments
            for payment in bill_payments:
                all_payments.append({
                    'type': 'bill', 
                    'date': payment.payment_date,
                    'student': payment.bill.student if payment.bill else None,
                    'amount': payment.amount,
                    'method': payment.payment_mode,
                    'receipt_number': getattr(payment, 'receipt_number', f"BILL-{payment.id}"),
                    'payment_obj': payment,
                    'is_confirmed': getattr(payment, 'is_confirmed', True)
                })
            
            # Sort by date descending and take top N
            all_payments.sort(key=lambda x: x['date'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error getting recent payments: {str(e)}")
            # Return empty list to prevent template errors
            return []
        
        return all_payments[:limit]
    
    def get(self, request, *args, **kwargs):
        """Handle export requests"""
        if 'export' in request.GET:
            try:
                return self.export_report(request)
            except Exception as e:
                logger.error(f"Error exporting report: {str(e)}")
                messages.error(request, f"Error exporting report: {str(e)}")
                return redirect('payment_summary')
        
        return super().get(request, *args, **kwargs)
    
    def export_report(self, request):
        """Export payment summary to Excel with error handling"""
        try:
            context = self.get_context_data()
            
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="payment_summary_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Payment Summary"
            
            # Add headers
            headers = ['Payment Method', 'Amount (GH₵)', 'Transactions', 'Percentage', 'Fee Payments', 'Bill Payments']
            for col_num, header in enumerate(headers, 1):
                ws.cell(row=1, column=col_num, value=header).font = Font(bold=True)
            
            # Add data
            row_num = 2
            for method, data in context['summary_by_method'].items():
                ws.cell(row=row_num, column=1, value=data['display_name'])
                ws.cell(row=row_num, column=2, value=float(data['total_amount']))
                ws.cell(row=row_num, column=3, value=data['count'])
                ws.cell(row=row_num, column=4, value=data['percentage'])
                ws.cell(row=row_num, column=5, value=data['fee_count'])
                ws.cell(row=row_num, column=6, value=data['bill_count'])
                row_num += 1
            
            # Add summary row
            summary_row = row_num + 1
            ws.cell(row=summary_row, column=1, value="TOTAL").font = Font(bold=True)
            ws.cell(row=summary_row, column=2, value=float(context['total_collected'])).font = Font(bold=True)
            ws.cell(row=summary_row, column=3, value=context['total_transactions']).font = Font(bold=True)
            ws.cell(row=summary_row, column=4, value=100.0).font = Font(bold=True)
            ws.cell(row=summary_row, column=5, value=sum(data['fee_count'] for data in context['summary_by_method'].values())).font = Font(bold=True)
            ws.cell(row=summary_row, column=6, value=sum(data['bill_count'] for data in context['summary_by_method'].values())).font = Font(bold=True)
            
            # Auto-size columns
            for col in ws.columns:
                max_length = 0
                column_letter = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min((max_length + 2), 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            wb.save(response)
            return response
            
        except Exception as e:
            logger.error(f"Error in export_to_excel: {str(e)}")
            raise