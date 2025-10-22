# Standard library imports
from datetime import datetime, timedelta
from calendar import monthcalendar
from urllib.parse import urlencode

# Django core imports
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, 
    DeleteView, View, TemplateView
)

# Third-party imports
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Local imports
from .base_views import is_admin, is_teacher, is_parent, is_student
from ..models import (
    # Core models
    ParentGuardian, Student, Teacher, 
    
    # Academic models
    Grade, ReportCard, StudentAttendance, AcademicTerm,
    
    # Fee models
    Fee, FeePayment,
    
    # Communication models
    ParentAnnouncement, ParentMessage, ParentEvent,
    
    # Configuration
    CLASS_LEVEL_CHOICES
)
from ..forms import (
    ParentGuardianAddForm, ParentFeePaymentForm, 
    ParentAttendanceFilterForm, ReportCardFilterForm
)

User = get_user_model()


class ParentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ParentGuardian
    form_class = ParentGuardianAddForm
    template_name = 'core/parents/parent_form.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_form_kwargs(self):
        """Prepare form kwargs with student_id"""
        kwargs = super().get_form_kwargs()
        student_id = self.kwargs.get('student_id')
        
        if student_id:
            kwargs['student_id'] = student_id
        
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student_id = self.kwargs.get('student_id')
        if student_id:
            context['student'] = get_object_or_404(Student, pk=student_id)
            context['student_id'] = student_id
        return context
    
    def form_valid(self, form):
        """Handle successful form submission with transaction safety"""
        try:
            with transaction.atomic():
                # Save the parent (the form handles user creation and student relationship)
                self.object = form.save()
                
                messages.success(self.request, 'Parent/Guardian added successfully')
                return super().form_valid(form)
                
        except Exception as e:
            messages.error(self.request, f'Error saving parent: {str(e)}')
            return self.form_invalid(form)
    
    def get_success_url(self):
        """Redirect to student detail page"""
        student_id = self.kwargs.get('student_id')
        if student_id:
            return reverse_lazy('student_detail', kwargs={'pk': student_id})
        return reverse_lazy('student_list')


class ParentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ParentGuardian
    form_class = ParentGuardianAddForm
    template_name = 'core/parents/parent_form.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_success_url(self):
        # Redirect to the first student's detail page
        if self.object.students.exists():
            return reverse_lazy('student_detail', kwargs={'pk': self.object.students.first().pk})
        return reverse_lazy('student_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Parent/Guardian updated successfully')
        return super().form_valid(form)


class ParentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ParentGuardian
    template_name = 'core/parents/parent_confirm_delete.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_success_url(self):
        if self.object.students.exists():
            return reverse_lazy('student_detail', kwargs={'pk': self.object.students.first().pk})
        return reverse_lazy('student_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Parent/Guardian deleted successfully')
        return super().delete(request, *args, **kwargs)


# Fee statement view for parents
class ParentFeeStatementView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Student
    template_name = 'finance/parent_fee_statement.html'
    
    def test_func(self):
        return self.request.user.parentguardian.students.filter(pk=self.kwargs['pk']).exists()
    
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
        return self.request.user.parentguardian.students.all().select_related('user')


class ParentChildDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Student
    template_name = 'core/parents/child_detail.html'
    context_object_name = 'child'
    
    def test_func(self):
        parent = self.request.user.parentguardian
        return parent.students.filter(pk=self.kwargs['pk']).exists()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        child = self.get_object()
        
        # Attendance stats
        context['present_count'] = child.attendances.filter(status='present').count()
        context['absent_count'] = child.attendances.filter(status='absent').count()
        context['late_count'] = child.attendances.filter(status='late').count()
        
        # Recent grades
        context['recent_grades'] = Grade.objects.filter(student=child).select_related('subject').order_by('-last_updated')[:5]
        
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
        children = self.request.user.parentguardian.students.all()
        queryset = Fee.objects.filter(student__in=children).select_related('student', 'category')
        
        # Apply filters
        payment_status = self.request.GET.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        # Order by due date and payment status
        return queryset.order_by('due_date', 'payment_status')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        children = self.request.user.parentguardian.students.all()
        
        # Summary statistics
        fees = Fee.objects.filter(student__in=children)
        context['total_payable'] = fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0
        context['total_paid'] = fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        context['total_balance'] = context['total_payable'] - context['total_paid']
        
        # Payment status counts
        context['paid_count'] = fees.filter(payment_status='PAID').count()
        context['partial_count'] = fees.filter(payment_status='PARTIAL').count()
        context['unpaid_count'] = fees.filter(payment_status='UNPAID').count()
        context['overdue_count'] = fees.filter(payment_status='OVERDUE').count()
        
        return context


class ParentFeeDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Fee
    template_name = 'core/parents/fee_detail.html'
    
    def test_func(self):
        parent = self.request.user.parentguardian
        return parent.students.filter(pk=self.get_object().student.pk).exists()
    
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
        return self.request.user.parentguardian.students.filter(pk=fee.student.pk).exists()
    
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
                    
                    messages.success(request, f'Payment of GH₵{amount} successfully recorded')
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
        children = self.request.user.parentguardian.students.all()
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
        children = self.request.user.parentguardian.students.all()
        
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
        
        # Calculate overall attendance percentage
        total_records = attendances.count()
        present_records = context['present_count']
        context['attendance_percentage'] = round((present_records / total_records * 100), 1) if total_records > 0 else 0
        
        return context


class ParentReportCardListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ReportCard
    template_name = 'core/parents/report_card_list.html'
    context_object_name = 'report_cards'
    
    def test_func(self):
        return hasattr(self.request.user, 'parentguardian') or hasattr(self.request.user, 'student')
    
    def get_queryset(self):
        user = self.request.user
        
        if hasattr(user, 'parentguardian'):
            children = user.parentguardian.students.all()
        elif hasattr(user, 'student'):
            children = Student.objects.filter(pk=user.student.pk)
        else:
            children = Student.objects.none()
            
        return ReportCard.objects.filter(
            student__in=children
        ).select_related('student').order_by('-academic_year', '-term')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if hasattr(user, 'parentguardian'):
            context['children'] = user.parentguardian.students.all()
        elif hasattr(user, 'student'):
            context['children'] = Student.objects.filter(pk=user.student.pk)
        else:
            context['children'] = Student.objects.none()
            
        return context


class ParentReportCardDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        """
        Check if the current user is authorized to view this report card.
        Only the parent of the student can view the report card.
        """
        if not is_parent(self.request.user):
            return False
            
        student_id = self.kwargs.get('student_id')
        parent = self.request.user.parentguardian
        
        # Check if the student belongs to this parent
        return parent.students.filter(pk=student_id).exists()
    
    def get(self, request, student_id, report_card_id=None):
        parent = request.user.parentguardian
        student = get_object_or_404(Student, pk=student_id)
        
        # Double-check permission (redundant but safe)
        if not parent.students.filter(pk=student_id).exists():
            raise PermissionDenied

        # Get report card if specified
        report_card = None
        if report_card_id:
            report_card = get_object_or_404(ReportCard, pk=report_card_id, student=student)
        
        # Get filtered grades
        grades = Grade.objects.filter(student=student).select_related('subject')
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
        
        # Safely calculate overall grade
        try:
            overall_grade = Grade.calculate_grade(average_score) if hasattr(Grade, 'calculate_grade') else 'N/A'
        except:
            overall_grade = 'N/A'
        
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
    """
    Parent Dashboard View with comprehensive child data and school information
    """
    if not is_parent(request.user):
        raise PermissionDenied("Access denied. Parent privileges required.")
    
    try:
        parent = request.user.parentguardian
        
        # Get all children for this parent with optimized queries
        children = parent.students.all().select_related('user')
        
        # Get current date info for filtering
        current_date = timezone.now().date()
        current_month = current_date.month
        current_year = current_date.year
        next_week = current_date + timedelta(days=7)
        
        # Process children data with proper error handling
        children_data = []
        total_recent_grades = 0
        total_unpaid_fees = 0
        total_attendance_records = 0
        
        for child in children:
            try:
                # Get recent grades (last 3 updated grades)
                recent_grades = Grade.objects.filter(
                    student=child
                ).select_related('subject').order_by('-last_updated')[:3]
                
                # Get attendance summary for current month with safe aggregation
                attendance_data = StudentAttendance.objects.filter(
                    student=child,
                    date__month=current_month,
                    date__year=current_year
                )
                
                attendance_summary = attendance_data.aggregate(
                    present=Count('id', filter=Q(status='present')),
                    absent=Count('id', filter=Q(status='absent')),
                    late=Count('id', filter=Q(status='late')),
                    excused=Count('id', filter=Q(status='excused')),
                    total=Count('id')
                )
                
                # Calculate attendance percentage safely
                total_attendance = attendance_summary['total'] or 0
                present_count = attendance_summary['present'] or 0
                attendance_percentage = 0
                if total_attendance > 0:
                    attendance_percentage = round((present_count / total_attendance) * 100, 1)
                
                # Get fee status with safe aggregation
                fee_data = Fee.objects.filter(
                    student=child,
                    payment_status__in=['unpaid', 'partial']
                )
                
                fee_summary = fee_data.aggregate(
                    total_due=Sum('balance'),
                    unpaid_count=Count('id'),
                    total_payable=Sum('amount_payable'),
                    total_paid=Sum('amount_paid')
                )
                
                # Handle None values in fee data
                total_due = fee_summary['total_due'] or 0
                unpaid_count = fee_summary['unpaid_count'] or 0
                total_payable = fee_summary['total_payable'] or 0
                total_paid = fee_summary['total_paid'] or 0
                
                # Update global counters
                total_recent_grades += len(recent_grades)
                if total_due > 0:
                    total_unpaid_fees += 1
                total_attendance_records += total_attendance
                
                # Calculate child's average grade if available
                child_grades = Grade.objects.filter(student=child)
                average_grade = child_grades.aggregate(avg=Avg('total_score'))['avg']
                average_grade = round(average_grade, 1) if average_grade else 0
                
                # Get performance level based on average grade
                performance_level = "No Data"
                if average_grade > 0:
                    if average_grade >= 80:
                        performance_level = "Excellent"
                    elif average_grade >= 70:
                        performance_level = "Very Good"
                    elif average_grade >= 60:
                        performance_level = "Good"
                    elif average_grade >= 50:
                        performance_level = "Satisfactory"
                    elif average_grade >= 40:
                        performance_level = "Fair"
                    else:
                        performance_level = "Needs Improvement"
                
                child_data = {
                    'child': child,
                    'recent_grades': recent_grades,
                    'attendance': {
                        'present': attendance_summary['present'] or 0,
                        'absent': attendance_summary['absent'] or 0,
                        'late': attendance_summary['late'] or 0,
                        'excused': attendance_summary['excused'] or 0,
                        'total': total_attendance,
                        'percentage': attendance_percentage
                    },
                    'fee_status': {
                        'total_due': total_due,
                        'unpaid_count': unpaid_count,
                        'total_payable': total_payable,
                        'total_paid': total_paid,
                        'balance': total_due
                    },
                    'academic_summary': {
                        'average_grade': average_grade,
                        'performance_level': performance_level,
                        'total_subjects': child_grades.count()
                    }
                }
                
                children_data.append(child_data)
                
            except Exception as e:
                # Log error but continue processing other children
                print(f"Error processing data for child {child.id}: {str(e)}")
                continue
        
        # Get child classes for filtering announcements and events
        child_classes = children.values_list('class_level', flat=True).distinct()
        
        # Get recent announcements with proper filtering
        recent_announcements = ParentAnnouncement.objects.filter(
            Q(target_type='ALL') | 
            Q(target_type='CLASS', target_class__in=child_classes) |
            Q(target_type='INDIVIDUAL', target_parents=parent)
        ).select_related('created_by').order_by('-created_at')[:5]
        
        # Get unread messages count
        unread_messages = ParentMessage.objects.filter(
            receiver=request.user,
            is_read=False
        ).count()
        
        # Get upcoming events (next 7 days)
        upcoming_events = ParentEvent.objects.filter(
            Q(is_whole_school=True) | Q(class_level__in=child_classes),
            start_date__gte=current_date,
            start_date__lte=next_week
        ).select_related('created_by').order_by('start_date')[:5]
        
        # Calculate dashboard statistics
        dashboard_stats = {
            'total_children': len(children_data),
            'total_recent_grades': total_recent_grades,
            'total_unpaid_fees': total_unpaid_fees,
            'total_attendance_records': total_attendance_records,
            'children_with_issues': sum(1 for child in children_data 
                                      if child['fee_status']['total_due'] > 0 or 
                                         child['attendance']['percentage'] < 80),
            'overall_attendance_rate': 0
        }
        
        # Calculate overall attendance rate
        total_present = sum(child['attendance']['present'] for child in children_data)
        total_attendance_days = sum(child['attendance']['total'] for child in children_data)
        if total_attendance_days > 0:
            dashboard_stats['overall_attendance_rate'] = round(
                (total_present / total_attendance_days) * 100, 1
            )
        
        context = {
            'parent': parent,
            'children_data': children_data,
            'dashboard_stats': dashboard_stats,
            'recent_announcements': recent_announcements,
            'unread_messages': unread_messages,
            'upcoming_events': upcoming_events,
            'current_date': current_date,
            'next_week': next_week,
            'has_children': len(children_data) > 0,
        }
        
        return render(request, 'core/parents/parent_dashboard.html', context)
        
    except Exception as e:
        # Generic error handling for critical failures
        print(f"Critical error in parent dashboard: {str(e)}")
        context = {
            'error': True,
            'error_message': 'Unable to load dashboard data. Please try again later.'
        }
        return render(request, 'core/parents/parent_dashboard.html', context)


class ParentAnnouncementListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ParentAnnouncement
    template_name = 'core/parents/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 10
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        parent = self.request.user.parentguardian
        children = parent.students.all()
        child_classes = children.values_list('class_level', flat=True).distinct()
        
        return ParentAnnouncement.objects.filter(
            Q(target_type='ALL') | 
            Q(target_type='CLASS', target_class__in=child_classes) |
            Q(target_type='INDIVIDUAL', target_parents=parent)
        ).select_related('created_by').order_by('-created_at')


class ParentMessageListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ParentMessage
    template_name = 'core/parents/message_list.html'
    context_object_name = 'messages'
    paginate_by = 20  # Added pagination
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        return ParentMessage.objects.filter(
            receiver=self.request.user
        ).select_related('sender', 'parent', 'teacher').order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get teachers for messaging
        children = self.request.user.parentguardian.students.all()
        context['teachers'] = Teacher.objects.filter(
            classassignment__class_level__in=children.values_list('class_level', flat=True)
        ).distinct()
        
        # Add unread count
        context['unread_count'] = self.get_queryset().filter(is_read=False).count()
        
        return context

class ParentMessageCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ParentMessage
    fields = ['receiver', 'subject', 'message']
    template_name = 'core/parents/message_form.html'
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_context_data(self, **kwargs):
        """Add teachers to the context for the recipient dropdown"""
        context = super().get_context_data(**kwargs)
        
        # Get the parent's children
        parent = self.request.user.parentguardian
        children = parent.students.all()
        
        # Get teachers who teach the parent's children
        context['teachers'] = Teacher.objects.filter(
            classassignment__class_level__in=children.values_list('class_level', flat=True)
        ).distinct().select_related('user')
        
        # Handle reply functionality
        reply_to = self.request.GET.get('reply_to')
        if reply_to:
            try:
                reply_user = User.objects.get(pk=reply_to)
                context['reply_to'] = reply_user
                # Pre-fill the receiver field
                context['form'].fields['receiver'].initial = reply_user
            except User.DoesNotExist:
                pass
        
        # Handle subject from reply
        subject = self.request.GET.get('subject')
        if subject:
            context['form'].fields['subject'].initial = subject
        
        return context
    
    def get_form(self, form_class=None):
        """Limit receiver choices to teachers and staff"""
        form = super().get_form(form_class)
        
        # Get the parent's children
        parent = self.request.user.parentguardian
        children = parent.students.all()
        
        # Get teachers who teach the parent's children
        teachers = Teacher.objects.filter(
            classassignment__class_level__in=children.values_list('class_level', flat=True)
        ).distinct()
        
        # Get staff users (admins, etc.)
        staff_users = User.objects.filter(
            Q(is_staff=True) | Q(is_superuser=True)
        ).exclude(pk=self.request.user.pk)
        
        # Combine teacher users and staff users
        allowed_users = User.objects.filter(
            Q(teacher__in=teachers) | Q(pk__in=staff_users.values_list('pk', flat=True))
        ).distinct()
        
        # Limit the receiver field choices
        form.fields['receiver'].queryset = allowed_users
        
        return form
    
    def form_valid(self, form):
        form.instance.sender = self.request.user
        form.instance.parent = self.request.user.parentguardian
        
        # Link teacher if message is to a teacher
        if hasattr(form.instance.receiver, 'teacher'):
            form.instance.teacher = form.instance.receiver.teacher
        
        messages.success(self.request, 'Message sent successfully')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('parent_messages')

class ParentCalendarView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/parents/calendar.html'
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent = self.request.user.parentguardian
        children = parent.students.all()
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


# PARENT PORTAL MANAGEMENT VIEWS FOR ADMIN/TEACHERS
class ParentDirectoryView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ParentGuardian
    template_name = 'core/parents/admin_parent_directory.html'
    context_object_name = 'parents'
    paginate_by = 20
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_queryset(self):
        queryset = ParentGuardian.objects.select_related('user').prefetch_related('students')
        
        # Apply filters
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(phone_number__icontains=search)
            )
        
        relationship = self.request.GET.get('relationship')
        if relationship:
            queryset = queryset.filter(relationship=relationship)
            
        return queryset.order_by('user__last_name', 'user__first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Parent engagement statistics
        parents = self.get_queryset()
        context['total_parents'] = parents.count()
        context['active_parents'] = parents.filter(user__last_login__isnull=False).count()
        context['parents_with_multiple_children'] = parents.annotate(
            child_count=Count('students')
        ).filter(child_count__gt=1).count()
        
        # Add filter form data
        context['search_term'] = self.request.GET.get('search', '')
        context['relationship_filter'] = self.request.GET.get('relationship', '')
        
        return context


class BulkParentMessageView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'core/parents/bulk_parent_message.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get(self, request):
        # Get statistics for the template
        total_parents = ParentGuardian.objects.count()
        parents_with_email = ParentGuardian.objects.filter(
            Q(email__isnull=False) & ~Q(email='')
        ).count()
        active_parents = ParentGuardian.objects.filter(
            user__last_login__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        context = {
            'classes': CLASS_LEVEL_CHOICES,
            'target_types': [
                ('ALL', 'All Parents'),
                ('CLASS', 'Specific Class'),
                ('SELECTED', 'Selected Parents')
            ],
            'total_parents': total_parents,
            'parents_with_email': parents_with_email,
            'active_parents': active_parents,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        target_type = request.POST.get('target_type')
        target_class = request.POST.get('target_class')
        selected_parents = request.POST.getlist('selected_parents')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        if not subject or not message:
            messages.error(request, 'Subject and message are required')
            return self.get(request)
        
        # Get target parents based on selection
        if target_type == 'ALL':
            parents = ParentGuardian.objects.all()
        elif target_type == 'CLASS' and target_class:
            parents = ParentGuardian.objects.filter(students__class_level=target_class).distinct()
        elif target_type == 'SELECTED' and selected_parents:
            parents = ParentGuardian.objects.filter(id__in=selected_parents)
        else:
            messages.error(request, 'Please select valid target parents')
            return self.get(request)
        
        # Create messages for each parent
        messages_created = 0
        for parent in parents:
            if parent.user:
                ParentMessage.objects.create(
                    sender=request.user,
                    receiver=parent.user,
                    parent=parent,
                    teacher=request.user.teacher if hasattr(request.user, 'teacher') else None,
                    subject=subject,
                    message=message
                )
                messages_created += 1
        
        messages.success(request, f'Message sent to {messages_created} parents')
        return redirect('parent_communication_log')


class ParentCommunicationLogView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ParentMessage
    template_name = 'core/parents/parent_communication_log.html'
    context_object_name = 'messages'
    paginate_by = 20
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_queryset(self):
        # Get all messages sent by admin/teachers to parents
        return ParentMessage.objects.filter(
            sender=self.request.user
        ).select_related('receiver', 'parent').order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Communication statistics
        messages = self.get_queryset()
        context['total_messages'] = messages.count()
        context['read_messages'] = messages.filter(is_read=True).count()
        context['unread_messages'] = messages.filter(is_read=False).count()
        
        # Response rate (simplified - count replies)
        parent_messages = ParentMessage.objects.filter(
            receiver=self.request.user,
            sender__parentguardian__isnull=False
        )
        context['response_count'] = parent_messages.count()
        
        return context


class ParentEngagementDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/parents/parent_engagement_dashboard.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Basic parent metrics
        total_parents = ParentGuardian.objects.count()
        parents_with_accounts = ParentGuardian.objects.filter(user__isnull=False).count()
        active_parents = ParentGuardian.objects.filter(
            user__last_login__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # Parent engagement by class
        class_engagement = []
        for class_level in CLASS_LEVEL_CHOICES:
            class_parents = ParentGuardian.objects.filter(
                students__class_level=class_level[0]
            ).distinct()
            active_class_parents = class_parents.filter(
                user__last_login__gte=timezone.now() - timedelta(days=30)
            )
            
            engagement_rate = (active_class_parents.count() / class_parents.count() * 100) if class_parents.count() > 0 else 0
            
            class_engagement.append({
                'class_level': class_level[1],
                'total_parents': class_parents.count(),
                'active_parents': active_class_parents.count(),
                'engagement_rate': round(engagement_rate, 1)
            })
        
        # Recent parent logins
        recent_logins = User.objects.filter(
            parentguardian__isnull=False,
            last_login__isnull=False
        ).order_by('-last_login')[:10]
        
        # Message statistics
        sent_messages = ParentMessage.objects.filter(sender=self.request.user).count()
        received_messages = ParentMessage.objects.filter(receiver=self.request.user).count()
        
        context.update({
            'total_parents': total_parents,
            'parents_with_accounts': parents_with_accounts,
            'active_parents': active_parents,
            'class_engagement': class_engagement,
            'recent_logins': recent_logins,
            'sent_messages': sent_messages,
            'received_messages': received_messages,
            'engagement_rate': round((active_parents / parents_with_accounts * 100) if parents_with_accounts > 0 else 0, 1)
        })
        
        return context