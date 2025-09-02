from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from io import BytesIO

from .base_views import *
from ..models import FeeCategory, Fee, FeePayment, AcademicTerm, Student
from ..forms import FeeCategoryForm, FeeForm, FeePaymentForm, FeeFilterForm, FeeStatusReportForm


# Fee management
class FeeCategoryListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = FeeCategory
    template_name = 'core/Finance/categories/fee_category_list.html'
    
    def test_func(self):
        return is_admin(self.request.user)

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
    
@api_view(['GET'])
def fee_category_detail(request, pk):
    try:
        category = FeeCategory.objects.get(pk=pk)
        serializer = FeeCategorySerializer(category)
        return Response(serializer.data)
    except FeeCategory.DoesNotExist:
        return Response(status=404)

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
        queryset = super().get_queryset().select_related('student', 'category')
        
        # Apply filters from GET parameters
        form = FeeFilterForm(self.request.GET)
        if form.is_valid():
            academic_year = form.cleaned_data.get('academic_year')
            term = form.cleaned_data.get('term')
            payment_status = form.cleaned_data.get('payment_status')
            category = form.cleaned_data.get('category')
            student = form.cleaned_data.get('student')
            
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
        context['total_payable'] = queryset.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0
        context['total_paid'] = queryset.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        context['total_balance'] = context['total_payable'] - context['total_paid']
        
        # Add all students for the modal - FIXED
        if is_admin(self.request.user) or is_teacher(self.request.user):
            context['all_students'] = Student.objects.filter(is_active=True).order_by('first_name', 'last_name')
        else:
            context['all_students'] = Student.objects.none()
        
        return context
class FeeDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Fee
    template_name = 'core/finance/fees/fee_detail.html'
    
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
        kwargs['fee_id'] = self.kwargs.get('fee_id')
        return kwargs
    
    def form_valid(self, form):
        with transaction.atomic():
            form.instance.recorded_by = self.request.user
            response = super().form_valid(form)
            
            # Update the parent fee record
            fee = form.instance.fee
            fee.amount_paid += form.instance.amount
            fee.save()
            
            messages.success(self.request, 'Payment recorded successfully')
            return response
    
    def get_success_url(self):
        return reverse_lazy('fee_detail', kwargs={'pk': self.object.fee.pk})

class FeePaymentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = FeePayment
    template_name = 'core/finance/fees/fee_payment_confirm_delete.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        with transaction.atomic():
            payment = self.get_object()
            fee = payment.fee
            
            # Deduct payment amount from fee before deletion
            fee.amount_paid -= payment.amount
            fee.save()
            
            messages.success(request, 'Payment record deleted successfully')
            return super().delete(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse_lazy('fee_detail', kwargs={'pk': self.object.fee.pk})

# Reports
class FeeReportView(LoginRequiredMixin, UserPassesTestMixin, View):
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
        
        # Calculate summary statistics
        summary = fees.aggregate(
            total_payable=Sum('amount_payable'),
            total_paid=Sum('amount_paid'),
            count=Count('id'),
            paid_count=Count('id', filter=Q(payment_status='PAID')),
            overdue_count=Count('id', filter=Q(payment_status='OVERDUE')),
        )
        
        context = {
            'form': form,
            'fees': fees.order_by('student__last_name', 'student__first_name'),
            'summary': summary,
        }
        
        if 'export' in request.GET:
            return self.export_to_excel(fees)

        return render(request, 'core/finance/fees/fee_report.html', context)

    def export_to_excel(self, queryset):
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="fee_report.xlsx"'
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Fee Report"
        
        # Add headers
        headers = [
            'Student ID', 'Student Name', 'Class', 
            'Fee Category', 'Amount Payable', 'Amount Paid', 
            'Balance', 'Payment Status', 'Due Date'
        ]
        
        for col_num, header in enumerate(headers, 1):
            col_letter = get_column_letter(col_num)
            ws[f'{col_letter}1'] = header
        
        # Add data
        for row_num, fee in enumerate(queryset, 2):
            ws[f'A{row_num}'] = fee.student.student_id
            ws[f'B{row_num}'] = fee.student.get_full_name()
            ws[f'C{row_num}'] = fee.student.get_class_level_display()
            ws[f'D{row_num}'] = str(fee.category)
            ws[f'E{row_num}'] = float(fee.amount_payable)
            ws[f'F{row_num}'] = float(fee.amount_paid)
            ws[f'G{row_num}'] = float(fee.balance)
            ws[f'H{row_num}'] = fee.get_payment_status_display()
            ws[f'I{row_num}'] = fee.due_date.strftime('%Y-%m-%d')
        
        # Auto-size columns
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2
            ws.column_dimensions[column].width = adjusted_width
        
        wb.save(response)
        return response
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)

# fee status report
class FeeStatusReportView(LoginRequiredMixin, UserPassesTestMixin, View):
    def get(self, request):
        # Initialize form with GET parameters
        form = FeeStatusReportForm(request.GET or None)
        
        # Get base queryset
        fees = Fee.objects.all().select_related('student', 'category')
        
        # Apply filters if form is valid
        if form.is_valid():
            date_range = form.cleaned_data.get('date_range')
            class_level = form.cleaned_data.get('class_level')
            category = form.cleaned_data.get('category')
            
            if date_range:
                start_date, end_date = date_range
                fees = fees.filter(date_recorded__range=(start_date, end_date))
            
            if class_level:
                fees = fees.filter(student__class_level=class_level)
                
            if category:
                fees = fees.filter(category=category)
        
        # Categorize fees by status
        paid_fees = fees.filter(payment_status='PAID')
        partial_fees = fees.filter(payment_status='PARTIAL')
        unpaid_fees = fees.filter(payment_status='UNPAID')
        overdue_fees = fees.filter(payment_status='OVERDUE')
        
        # Calculate summaries
        summary = {
            'total_payable': fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0,
            'total_paid': fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
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
            'summary': summary
        }
        
        if request.GET.get('export'):
            return self.export_report(context)
            
        return render(request, 'finance/fees/fee_status_report.html', context)
    
    def export_report(self, context):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="fee_status_report.xlsx"'
        
        wb = Workbook()
        
        # Create sheets for each status
        self._create_sheet(wb, 'Paid Fees', context['paid_fees'])
        self._create_sheet(wb, 'Partial Payments', context['partial_fees'])
        self._create_sheet(wb, 'Unpaid Fees', context['unpaid_fees'])
        self._create_sheet(wb, 'Overdue Fees', context['overdue_fees'])
        
        wb.save(response)
        return response
    
    def _create_sheet(self, wb, title, queryset):
        ws = wb.create_sheet(title=title)
        
        headers = [
            'Student ID', 'Student Name', 'Class', 
            'Fee Category', 'Amount Payable', 'Amount Paid',
            'Balance', 'Due Date', 'Status'
        ]
        
        ws.append(headers)
        
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
                fee.get_payment_status_display()
            ])
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)

class FeeDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'finance/fees/fee_dashboard.html'
    
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
            
            context.update({
                'total_payable': fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0,
                'total_paid': fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
                'payment_status_distribution': self.get_payment_status_distribution(fees),
                'class_level_stats': self.get_class_level_stats(fees),
                'recent_payments': FeePayment.objects.order_by('-payment_date')[:10]
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
                    student.class_level not in category.class_levels.split(',')):
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
                    recorded_by=recorded_by  # Use actual user instead of system user
                )
                created_count += 1
                
    return created_count
