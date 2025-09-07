from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from django.views.generic import ListView, DetailView, View
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponse
from django.db.models import Sum, Count, Q, Max
from django.contrib import messages
from decimal import Decimal

from .base_views import is_admin, is_teacher, is_student
from ..models import Bill, BillItem, FeeCategory, Student, AcademicTerm, ClassAssignment, Fee
from ..forms import BillGenerationForm

class BillListView(LoginRequiredMixin, ListView):
    model = Bill
    template_name = 'core/finance/bills/bill_list.html'
    paginate_by = 20
    context_object_name = 'bills'
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('student')
        
        # Apply filters from GET parameters
        academic_year = self.request.GET.get('academic_year')
        term = self.request.GET.get('term')
        status = self.request.GET.get('status')
        
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        if term:
            queryset = queryset.filter(term=term)
        if status:
            queryset = queryset.filter(status=status)
        
        # Apply user-specific filters
        if is_student(self.request.user):
            queryset = queryset.filter(student=self.request.user.student)
        elif is_teacher(self.request.user):
            # Get classes taught by this teacher
            class_levels = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            queryset = queryset.filter(student__class_level__in=class_levels)
        
        return queryset.order_by('-issue_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add statistics to context
        queryset = self.get_queryset()
        context.update({
            'total_bills': queryset.count(),
            'paid_bills': queryset.filter(status='paid').count(),
            'outstanding_bills': queryset.filter(status__in=['issued', 'partial']).count(),
            'overdue_bills': queryset.filter(status='overdue').count(),
            'is_admin': is_admin(self.request.user),
        })
        
        return context

class BillDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Bill
    template_name = 'core/finance/bills/bill_detail.html'
    context_object_name = 'bill'
    
    def test_func(self):
        bill = self.get_object()
        if is_admin(self.request.user):
            return True
        elif is_teacher(self.request.user):
            # Check if teacher teaches this student's class
            return ClassAssignment.objects.filter(
                class_level=bill.student.class_level,
                teacher=self.request.user.teacher
            ).exists()
        elif is_student(self.request.user):
            return bill.student == self.request.user.student
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_admin'] = is_admin(self.request.user)
        context['fees'] = Fee.objects.filter(bill=self.object)
        return context

# In bill_views.py, update the get method
class BillGenerateView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'core/finance/bills/bill_generate.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get(self, request):
        form = BillGenerationForm()
        
        # Import CLASS_LEVEL_CHOICES from models
        from ..models import CLASS_LEVEL_CHOICES
        
        context = {
            'form': form,
            'student_count': Student.objects.filter(is_active=True).count(),
            'fee_category_count': FeeCategory.objects.filter(is_active=True, is_mandatory=True).count(),
            'class_level_choices': CLASS_LEVEL_CHOICES,  # Use the imported constant
            'recent_generations': Bill.objects.values('academic_year', 'term')
                .annotate(bills_created=Count('id'), created_at=Max('issue_date'))
                .order_by('-created_at')[:5]
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        form = BillGenerationForm(request.POST)
        
        # Import CLASS_LEVEL_CHOICES from models
        from ..models import CLASS_LEVEL_CHOICES
        
        if form.is_valid():
            academic_year = form.cleaned_data['academic_year']
            term = form.cleaned_data['term']
            class_levels = form.cleaned_data.get('class_levels', [])
            due_date = form.cleaned_data['due_date']
            notes = form.cleaned_data.get('notes', '')
            skip_existing = form.cleaned_data.get('skip_existing', True)
            
            try:
                bills_created = generate_term_bills(
                    academic_year=academic_year,
                    term=term,
                    class_levels=class_levels,
                    due_date=due_date,
                    notes=notes,
                    skip_existing=skip_existing,
                    request_user=request.user
                )
                
                messages.success(
                    request, 
                    f'Successfully generated {bills_created} bills for {academic_year} Term {term}'
                )
                return redirect('bill_list')
                
            except Exception as e:
                messages.error(
                    request, 
                    f'Error generating bills: {str(e)}'
                )
        
        context = {
            'form': form,
            'student_count': Student.objects.filter(is_active=True).count(),
            'fee_category_count': FeeCategory.objects.filter(is_active=True, is_mandatory=True).count(),
            'class_level_choices': CLASS_LEVEL_CHOICES,  # Use the imported constant
        }
        
        return render(request, self.template_name, context)

class BillPaymentView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to handle bill payments"""
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def post(self, request, pk):
        bill = get_object_or_404(Bill, pk=pk)
        
        # Process payment logic here
        # This would typically create a FeePayment record and update bill status
        
        messages.success(request, f'Payment recorded for bill #{bill.bill_number}')
        return redirect('bill_detail', pk=bill.pk)

class BillCancelView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to cancel a bill"""
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def post(self, request, pk):
        bill = get_object_or_404(Bill, pk=pk)
        
        if bill.status != 'cancelled':
            bill.status = 'cancelled'
            bill.save()
            messages.success(request, f'Bill #{bill.bill_number} has been cancelled')
        else:
            messages.warning(request, f'Bill #{bill.bill_number} is already cancelled')
        
        return redirect('bill_detail', pk=bill.pk)