from ..models import ParentAnnouncement, ParentMessage, ParentEvent
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Avg
from urllib.parse import urlencode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


# Add these imports at the top of the file
from ..models import Teacher
from django.utils import timezone
from django.db.models import Q
from calendar import monthcalendar
from datetime import datetime

from .base_views import *
from ..models import ParentGuardian, Student, Fee, StudentAttendance, Grade, ReportCard, FeePayment
from ..forms import ParentGuardianForm, ParentFeePaymentForm, ParentAttendanceFilterForm, ReportCardFilterForm
#PARENTS RELATED VIEWS
class ParentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ParentGuardian
    form_class = ParentGuardianForm
    template_name = 'core/parents/parent_form.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_form_kwargs(self):
        """Prepare form kwargs with student_id and proper initial data"""
        kwargs = super().get_form_kwargs()
        student_id = self.kwargs.get('student_id')
        
        if student_id:
            # Ensure student exists before proceeding
            student = get_object_or_404(Student, pk=student_id)
            kwargs['student_id'] = student_id
            
            # Initialize form data if not present
            if 'data' not in kwargs:
                kwargs['data'] = {}
            
            # Create a mutable copy if needed
            if not isinstance(kwargs['data'], dict):
                kwargs['data'] = kwargs['data'].copy()
            
            # Set student in form data if not already set
            if 'student' not in kwargs['data']:
                kwargs['data']['student'] = student_id
            
            # Set initial student if in GET request
            if self.request.method == 'GET':
                kwargs['initial'] = kwargs.get('initial', {})
                kwargs['initial']['student'] = student_id
        
        return kwargs
    
    def form_valid(self, form):
        """Handle successful form submission with transaction safety"""
        from django.db import transaction
        
        try:
            with transaction.atomic():
                student_id = self.kwargs.get('student_id')
                
                # Debug: Print form data before save
                print("\n=== BEFORE SAVE ===")
                print("Form data:", form.cleaned_data)
                print("Student ID from URL:", student_id)
                print("Form instance student:", getattr(form.instance, 'student', None))
                
                # Ensure student is set
                if student_id and not form.instance.student_id:
                    form.instance.student = get_object_or_404(Student, pk=student_id)
                
                # Validate model before save
                form.instance.full_clean()
                
                # Save the instance
                self.object = form.save()
                
                # Debug: Print after save
                print("\n=== AFTER SAVE ===")
                print("Saved parent ID:", self.object.id)
                print("Associated student:", self.object.student)
                print("Database record:", ParentGuardian.objects.filter(id=self.object.id).exists())
                
                messages.success(self.request, 'Parent/Guardian added successfully')
                return super().form_valid(form)
                
        except Exception as e:
            # Detailed error logging
            import traceback
            print("\n=== SAVE ERROR ===")
            print("Error:", str(e))
            print("Traceback:", traceback.format_exc())
            
            # Form-specific errors
            if hasattr(e, 'error_dict'):
                for field, errors in e.error_dict.items():
                    for error in errors:
                        messages.error(self.request, f"{field}: {error}")
            else:
                messages.error(self.request, f'Error saving parent: {str(e)}')
            
            return self.form_invalid(form)
    
    def get_success_url(self):
        """Ensure we have a valid student relationship before redirecting"""
        if not hasattr(self.object, 'student'):
            messages.error(self.request, 'Parent saved but student relationship missing!')
            return reverse_lazy('student_list')
        return reverse_lazy('student_detail', kwargs={'pk': self.object.student.pk})
    
    def form_invalid(self, form):
        """Enhanced invalid form handling"""
        print("\n=== FORM INVALID ===")
        print("Form errors:", form.errors.as_json())
        print("Non-field errors:", form.non_field_errors())
        
        # Add field-specific errors to messages
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        
        return super().form_invalid(form)

class ParentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ParentGuardian
    form_class = ParentGuardianForm
    template_name = 'core/parents/parent_form.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('student_detail', kwargs={'pk': self.object.student.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Parent/Guardian updated successfully')
        return super().form_valid(form)

class ParentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ParentGuardian
    template_name = 'core/parents/parent_confirm_delete.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('student_detail', kwargs={'pk': self.object.student.pk})
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Parent/Guardian deleted successfully')
        return super().delete(request, *args, **kwargs)
    
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    student = self.get_object()
    
    # Debug: Check parent count before adding to context
    parent_count = student.parents.count()
    print(f"DEBUG: Found {parent_count} parents for student {student.id}")
    
    context['parents'] = student.parents.all()
    context['fees'] = student.fees.all().order_by('-academic_year', '-term')
    context['grades'] = Grade.objects.filter(student=student).order_by('subject')
    return context

# Fee statement view for parents
class ParentFeeStatementView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Student
    template_name = 'finance/parent_fee_statement.html'
    
    def test_func(self):
        return self.request.user.parentguardian.student.filter(pk=self.kwargs['pk']).exists()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()
        
        # Get all fees ordered by academic year and term
        fees = Fee.objects.filter(student=student).order_by('-academic_year', '-term')
        
        # Calculate totals
        total_payable = fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0
        total_paid = fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        
        context.update({
            'fees': fees,
            'total_payable': total_payable,
            'total_paid': total_paid,
        })
        return context


class ParentChildrenListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Student
    template_name = 'core/parents/children_list.html'
    context_object_name = 'children'
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        # This will work with either ForeignKey or ManyToMany
        if hasattr(self.request.user.parentguardian, 'student'):
            # For ManyToMany
            return self.request.user.parentguardian.student.all()
        else:
            # For ForeignKey (single child)
            return Student.objects.filter(parents=self.request.user.parentguardian)

class ParentChildDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Student
    template_name = 'core/parents/child_detail.html'
    context_object_name = 'child'
    
    def test_func(self):
        parent = self.request.user.parentguardian
        return parent.student.filter(pk=self.kwargs['pk']).exists()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        child = self.get_object()
        
        # Attendance stats
        context['present_count'] = child.attendances.filter(status='present').count()
        context['absent_count'] = child.attendances.filter(status='absent').count()
        context['late_count'] = child.attendances.filter(status='late').count()
        
        # Recent grades
        context['recent_grades'] = Grade.objects.filter(student=child).order_by('-updated_at')[:5]
        
        # Fee summary
        fees = Fee.objects.filter(student=child)
        context['total_payable'] = fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0
        context['total_paid'] = fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        context['total_balance'] = context['total_payable'] - context['total_paid']
        
        return context

class ParentFeeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Fee
    template_name = 'core/parents/fee_list.html'
    context_object_name = 'fees'
    paginate_by = 10
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        children = self.request.user.parentguardian.student.all()
        queryset = Fee.objects.filter(student__in=children).select_related('student', 'category')
        
        # Apply filters
        payment_status = self.request.GET.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
            
        return queryset.order_by('-date_recorded')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        children = self.request.user.parentguardian.student.all()
        
        # Summary statistics
        fees = Fee.objects.filter(student__in=children)
        context['total_payable'] = fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0
        context['total_paid'] = fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        context['total_balance'] = context['total_payable'] - context['total_paid']
        
        return context

class ParentFeeDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Fee
    template_name = 'core/parents/fee_detail.html'
    
    def test_func(self):
        parent = self.request.user.parentguardian
        return parent.student.filter(pk=self.get_object().student.pk).exists()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payments'] = self.object.payments.all().order_by('-payment_date')
        return context

class ParentFeePaymentView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'core/parents/fee_payment.html'
    
    def test_func(self):
        if not is_parent(self.request.user):
            return False
        fee = get_object_or_404(Fee, pk=self.kwargs['pk'])
        return self.request.user.parentguardian.student.filter(pk=fee.student.pk).exists()
    
    def get(self, request, pk):
        fee = get_object_or_404(Fee, pk=pk)
        form = ParentFeePaymentForm(initial={'amount': fee.balance})
        return render(request, self.template_name, {'fee': fee, 'form': form})
    
    def post(self, request, pk):
        fee = get_object_or_404(Fee, pk=pk)
        form = ParentFeePaymentForm(request.POST)
        
        if form.is_valid():
            amount = form.cleaned_data['amount']
            payment_method = form.cleaned_data['payment_method']
            
            if amount > fee.balance:
                form.add_error('amount', 'Payment amount cannot exceed the balance')
            else:
                with transaction.atomic():
                    # Create payment record
                    payment = FeePayment.objects.create(
                        fee=fee,
                        amount=amount,
                        payment_method=payment_method,
                        recorded_by=request.user,
                        notes=f"Online payment by parent {request.user.get_full_name()}"
                    )
                    
                    # Update fee record
                    fee.amount_paid += amount
                    fee.save()
                    
                    messages.success(request, f'Payment of {amount} successfully recorded')
                    return redirect('parent_fee_detail', pk=fee.pk)
        
        return render(request, self.template_name, {'fee': fee, 'form': form})

class ParentAttendanceListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = StudentAttendance
    template_name = 'core/parents/attendance_list.html'
    context_object_name = 'attendances'
    paginate_by = 20
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        children = self.request.user.parentguardian.student.all()
        queryset = StudentAttendance.objects.filter(
            student__in=children
        ).select_related('student', 'term', 'period').order_by('-date')
        
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        student_id = self.request.GET.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
            
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
            
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        children = self.request.user.parentguardian.student.all()
        
        # Add filter form
        context['filter_form'] = ParentAttendanceFilterForm(
            initial={
                'student': self.request.GET.get('student'),
                'status': self.request.GET.get('status'),
                'date_from': self.request.GET.get('date_from'),
                'date_to': self.request.GET.get('date_to'),
            }
        )
        context['children'] = children
        
        # Calculate summary statistics
        attendances = self.get_queryset()
        context['present_count'] = attendances.filter(status='present').count()
        context['absent_count'] = attendances.filter(status='absent').count()
        context['late_count'] = attendances.filter(status='late').count()
        context['excused_count'] = attendances.filter(status='excused').count()
        
        return context

class ParentReportCardListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ReportCard
    template_name = 'core/parents/report_card_list.html'
    context_object_name = 'report_cards'
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        children = self.request.user.parentguardian.student.all()
        return ReportCard.objects.filter(
            student__in=children
        ).order_by('-academic_year', '-term')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['children'] = self.request.user.parentguardian.student.all()
        return context

class ParentReportCardDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    def get(self, request, student_id, report_card_id=None):
        parent = request.user.parentguardian
        student = get_object_or_404(Student, pk=student_id)
        
        # Check if student belongs to parent
        if not parent.student.filter(pk=student_id).exists():
            raise PermissionDenied
        
        # Get report card if specified
        report_card = None
        if report_card_id:
            report_card = get_object_or_404(ReportCard, pk=report_card_id, student=student)
        
        # Get filtered grades
        grades = Grade.objects.filter(student=student)
        if report_card:
            grades = grades.filter(
                academic_year=report_card.academic_year,
                term=report_card.term
            )
        else:
            # Apply filters from GET parameters
            form = ReportCardFilterForm(request.GET)
            if form.is_valid():
                if form.cleaned_data.get('academic_year'):
                    grades = grades.filter(academic_year=form.cleaned_data['academic_year'])
                if form.cleaned_data.get('term'):
                    grades = grades.filter(term=form.cleaned_data['term'])
        
        grades = grades.order_by('subject')
        
        # Calculate average
        aggregates = grades.aggregate(avg_score=Avg('total_score'))
        average_score = aggregates['avg_score'] or 0
        overall_grade = Grade.calculate_grade(average_score) if hasattr(Grade, 'calculate_grade') else 'N/A'
        
        context = {
            'student': student,
            'grades': grades,
            'average_score': round(float(average_score), 2),
            'overall_grade': overall_grade,
            'report_card': report_card,
            'form': ReportCardFilterForm(request.GET) if not report_card else None,
        }
        
        if 'pdf' in request.GET:
            return self.generate_pdf(context)
        
        return render(request, 'core/parents/report_card_detail.html', context)
    
    def generate_pdf(self, context):
        response = HttpResponse(content_type='application/pdf')
        filename = f"Report_Card_{context['student'].student_id}"
        if context['report_card']:
            filename += f"_{context['report_card'].academic_year}_Term{context['report_card'].term}"
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        
        p = canvas.Canvas(response, pagesize=letter)
        width, height = letter
        
        # PDF content
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, height - 100, f"Report Card for {context['student'].get_full_name()}")
        
        # Add more content as needed
        p.showPage()
        p.save()
        return response
    
@login_required
def parent_dashboard(request):
    if not is_parent(request.user):
        raise PermissionDenied
    
    parent = request.user.parentguardian
    children = parent.student.all()  # This should work if your relationship is set up correctly
    
    # Get recent activities
    recent_grades = Grade.objects.filter(student__in=children).order_by('-updated_at')[:5]
    recent_attendances = StudentAttendance.objects.filter(student__in=children).order_by('-date')[:5]
    unpaid_fees = Fee.objects.filter(student__in=children, payment_status='UNPAID').order_by('due_date')
    
    context = {
        'parent': parent,
        'children': children,
        'recent_grades': recent_grades,
        'recent_attendances': recent_attendances,
        'unpaid_fees': unpaid_fees,
    }
    return render(request, 'core/parents/parent_dashboard.html', context)


# Parent Dashboard and related views
class ParentDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/parents/parent_dashboard.html'
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent = self.request.user.parentguardian
        children = parent.student.all()
        
        # Get upcoming events (next 7 days)
        from datetime import datetime, timedelta
        next_week = timezone.now() + timedelta(days=7)
        
        # Get events for all classes of the parent's children
        child_classes = children.values_list('class_level', flat=True).distinct()
        context['upcoming_events'] = ParentEvent.objects.filter(
            Q(is_whole_school=True) | Q(class_level__in=child_classes),
            start_date__gte=timezone.now(),
            start_date__lte=next_week
        ).order_by('start_date')[:5]
        
        # Get recent announcements
        context['recent_announcements'] = ParentAnnouncement.objects.filter(
            Q(target_type='ALL') | 
            Q(target_type='CLASS', target_class__in=child_classes) |
            Q(target_type='INDIVIDUAL', target_parents=parent)
        ).order_by('-created_at')[:5]
        
        # Get unread messages
        context['unread_messages'] = ParentMessage.objects.filter(
            receiver=self.request.user,
            is_read=False
        ).count()
        
        # Get recent grades for all children
        context['recent_grades'] = Grade.objects.filter(
            student__in=children
        ).select_related('student', 'subject').order_by('-last_updated')[:5]
        
        # Get attendance summary for all children
        context['attendance_summary'] = StudentAttendance.objects.filter(
            student__in=children,
            date__month=timezone.now().month
        ).values('status').annotate(count=Count('id'))
        
        # Get fee summary
        context['fee_summary'] = {
            'total_due': Fee.objects.filter(
                student__in=children,
                payment_status__in=['unpaid', 'partial']
            ).aggregate(Sum('balance'))['balance__sum'] or 0,
            'overdue': Fee.objects.filter(
                student__in=children,
                payment_status='overdue'
            ).count()
        }
        
        context['children'] = children
        context['parent'] = parent
        
        return context

class ParentAnnouncementListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ParentAnnouncement
    template_name = 'core/parents/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 10
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        parent = self.request.user.parentguardian
        children = parent.student.all()
        child_classes = children.values_list('class_level', flat=True).distinct()
        
        return ParentAnnouncement.objects.filter(
            Q(target_type='ALL') | 
            Q(target_type='CLASS', target_class__in=child_classes) |
            Q(target_type='INDIVIDUAL', target_parents=parent)
        ).order_by('-created_at')

class ParentMessageListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ParentMessage
    template_name = 'core/parents/message_list.html'
    context_object_name = 'messages'
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        return ParentMessage.objects.filter(
            receiver=self.request.user
        ).order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get teachers for messaging
        children = self.request.user.parentguardian.student.all()
        context['teachers'] = Teacher.objects.filter(
            classassignment__class_level__in=children.values_list('class_level', flat=True)
        ).distinct()
        return context

class ParentMessageCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ParentMessage
    fields = ['receiver', 'subject', 'message']
    template_name = 'core/parents/message_form.html'
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def form_valid(self, form):
        form.instance.sender = self.request.user
        form.instance.parent = self.request.user.parentguardian
        
        # Link teacher if message is to a teacher
        if hasattr(form.instance.receiver, 'teacher'):
            form.instance.teacher = form.instance.receiver.teacher
        
        messages.success(self.request, 'Message sent successfully')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('parent_message_list')

class ParentCalendarView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/parents/calendar.html'
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent = self.request.user.parentguardian
        children = parent.student.all()
        child_classes = children.values_list('class_level', flat=True).distinct()
        
        # Get events
        context['events'] = ParentEvent.objects.filter(
            Q(is_whole_school=True) | Q(class_level__in=child_classes),
            start_date__gte=timezone.now()
        ).order_by('start_date')
        
        # Calendar data for month view
        today = timezone.now()
        context['current_month'] = today
        context['today'] = today
        
        # Generate calendar data
        cal = monthcalendar(today.year, today.month)
        calendar_data = []
        
        for week in cal:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append({'date': None, 'events': []})
                else:
                    day_date = datetime(today.year, today.month, day).date()
                    day_events = ParentEvent.objects.filter(
                        Q(is_whole_school=True) | Q(class_level__in=child_classes),
                        start_date__date=day_date
                    )
                    week_data.append({'date': day_date, 'events': day_events})
            calendar_data.append(week_data)
        
        context['calendar_data'] = calendar_data
        
        return context

class ParentMessageDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = ParentMessage
    template_name = 'core/parents/message_detail.html'
    context_object_name = 'message'
    
    def test_func(self):
        message = self.get_object()
        return message.receiver == self.request.user or message.sender == self.request.user
    
    def get(self, request, *args, **kwargs):
        # Mark as read when viewed
        message = self.get_object()
        if message.receiver == request.user and not message.is_read:
            message.is_read = True
            message.save()
        return super().get(request, *args, **kwargs)



















