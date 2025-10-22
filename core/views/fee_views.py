# Correct import section at the top of fee_views.py
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q, Avg
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font
from io import BytesIO

from .base_views import is_admin, is_teacher, is_student
from ..models import FeeCategory, Fee, FeePayment, AcademicTerm, Student, ClassAssignment, Bill
from ..forms import FeeCategoryForm, FeeForm, FeePaymentForm, FeeFilterForm, FeeStatusReportForm
from django.contrib import messages


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
        
        # Fix: Use lowercase statuses for counting
        paid_count = queryset.filter(payment_status='paid').count()
        pending_count = queryset.filter(payment_status__in=['unpaid', 'partial', 'overdue']).count()
        
        context.update({
            'total_payable': total_payable,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'paid_count': paid_count,
            'pending_count': pending_count,
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
        
        print(f"DEBUG: Recorded by: {form.instance.recorded_by}")
        print(f"DEBUG: Payment amount: {form.instance.amount}")
        print(f"DEBUG: Payment mode: {form.instance.payment_mode}")
        print(f"DEBUG: Payment date: {form.instance.payment_date}")
        
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
                
                # Update payment status
                if fee.balance <= 0:
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
                
                messages.success(self.request, f'Payment of GH₵{form.instance.amount:.2f} recorded successfully for {fee.student.get_full_name()}')
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
            
            # Update payment status
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