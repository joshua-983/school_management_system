# Standard library imports
from datetime import datetime, timedelta
from calendar import monthcalendar
from urllib.parse import urlencode
import logging
from core.views.base_views import ParentListView
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, Prefetch
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

from core.permissions import is_admin, is_teacher, is_parent, is_student
from core.utils.logger import log_parent_action, log_parent_error, log_view_exception, log_database_queries

from ..models import (
    # Core models
    ParentGuardian, Student, Teacher, 
    
    # Academic models
    Grade, ReportCard, StudentAttendance, AcademicTerm,
    
    # Fee models
    Fee, FeePayment,
    
    # Communication models
    ParentAnnouncement, ParentMessage, ParentEvent,
    # Announcement models
    Announcement, UserAnnouncementView,
    
    # Configuration
    CLASS_LEVEL_CHOICES
)
from ..forms import (
    ParentGuardianAddForm, ParentFeePaymentForm, 
    ParentAttendanceFilterForm, ReportCardFilterForm
)

logger = logging.getLogger(__name__)

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


class ParentFeeListView(ParentListView):
    """Display list of fees for parent's children"""
    model = Fee
    context_object_name = 'fees'
    template_name = 'core/parents/fee_list.html'  # Keep existing template
    
    def get_queryset(self):
        """Get fees for parent's children with optimization"""
        queryset = super().get_queryset()
        return queryset.select_related('student', 'category').order_by('due_date', 'payment_status')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Use aggregated query for stats
        fees = self.get_queryset()
        context['total_payable'] = fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0
        context['total_paid'] = fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        context['total_balance'] = context['total_payable'] - context['total_paid']
        
        # Get status counts in single query
        status_counts = fees.values('payment_status').annotate(
            count=Count('id')
        )
        
        # Convert to dictionary for template
        status_dict = {item['payment_status']: item['count'] for item in status_counts}
        context['paid_count'] = status_dict.get('PAID', 0)
        context['partial_count'] = status_dict.get('PARTIAL', 0)
        context['unpaid_count'] = status_dict.get('UNPAID', 0)
        context['overdue_count'] = status_dict.get('OVERDUE', 0)
        
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
        Secure permission check to ensure parents can only view their own children's report cards
        """
        if not is_parent(self.request.user):
            return False
            
        student_id = self.kwargs.get('student_id')
        report_card_id = self.kwargs.get('report_card_id')
        parent = self.request.user.parentguardian
        
        # Check if the student belongs to this parent
        student_belongs_to_parent = parent.students.filter(pk=student_id).exists()
        
        # If a specific report card is requested, verify it belongs to the student
        if report_card_id and student_belongs_to_parent:
            report_card_belongs_to_student = ReportCard.objects.filter(
                pk=report_card_id, 
                student_id=student_id
            ).exists()
            return report_card_belongs_to_student
        
        return student_belongs_to_parent
    
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


# Update the parent_dashboard function in my_views/parents_views.py
@login_required
@log_view_exception("parent_dashboard")
@log_database_queries
def parent_dashboard(request):
    """Optimized Parent Dashboard"""
    if not is_parent(request.user):
        raise PermissionDenied("Access denied: Parent privileges required")
    
    try:
        parent = request.user.parentguardian
        
        # Log dashboard access
        log_parent_action("Dashboard accessed", user=request.user, status='success')
        
        # Get optimized children data
        from core.utils.query_optimizer import ParentQueryOptimizer
        
        children = parent.students.all()
        optimized_children = ParentQueryOptimizer.optimize_child_queries(children)
        
        # Prepare children data using optimized queries
        children_data = []
        for child in optimized_children:
            try:
                child_summary = ParentQueryOptimizer.get_child_summary_stats(child)
                
                children_data.append({
                    'child': child,
                    **child_summary
                })
            except Exception as e:
                log_parent_error(
                    f"Error processing child data: {str(e)}",
                    user=request.user,
                    extra={'child_id': child.id}
                )
                continue
        
        # Get aggregated stats (efficient)
        aggregated_stats = ParentQueryOptimizer.get_aggregated_stats(parent)
        
        # Get other data (announcements, events, messages)
        child_classes = children.values_list('class_level', flat=True).distinct()
        
        # Optimize these queries too
        from core.models import ParentAnnouncement, ParentMessage, ParentEvent
        from django.db.models import Prefetch
        
        recent_announcements = ParentAnnouncement.objects.filter(
            Q(target_type='ALL') | 
            Q(target_type='CLASS', target_class__in=child_classes) |
            Q(target_type='INDIVIDUAL', target_parents=parent)
        ).select_related('created_by').order_by('-created_at')[:5]
        
        unread_messages = ParentMessage.objects.filter(
            receiver=request.user,
            is_read=False
        ).count()
        
        upcoming_events = ParentEvent.objects.filter(
            Q(is_whole_school=True) | Q(class_level__in=child_classes),
            start_date__gte=timezone.now(),
            start_date__lte=timezone.now() + timedelta(days=30)
        ).select_related('created_by').order_by('start_date')[:5]
        
        context = {
            'parent': parent,
            'children_data': children_data,
            'total_children': len(children_data),
            'dashboard_stats': aggregated_stats,  # Use aggregated stats
            'recent_announcements': recent_announcements,
            'unread_messages': unread_messages,
            'upcoming_events': upcoming_events,
            'current_academic_year': get_current_academic_year(),
        }
        
        return render(request, 'core/parents/parent_dashboard.html', context)
        
    except Exception as e:
        log_parent_error(
            "Critical error in parent dashboard",
            user=request.user,
            exc_info=True
        )
        messages.error(request, "Error loading dashboard data. Please try again.")
        return render(request, 'core/parents/parent_dashboard.html', {})

class ParentAnnouncementListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Announcement list view specifically for parents using the main Announcement model"""
    model = Announcement
    template_name = 'core/parents/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 10
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        parent = self.request.user.parentguardian
        
        # Get all class levels of parent's children
        children_classes = parent.students.values_list('class_level', flat=True).distinct()
        
        # Get announcements that are either:
        # 1. Targeted to the parent's children's classes
        # 2. School-wide announcements (empty target_class_levels)
        # 3. Active and within date range
        from django.utils import timezone
        from django.db.models import Q
        
        queryset = Announcement.objects.filter(
            Q(target_class_levels__in=children_classes) |
            Q(target_class_levels='') |
            Q(target_class_levels__isnull=True)
        ).filter(
            is_active=True,
            start_date__lte=timezone.now(),
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
        ).select_related('created_by').order_by('-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent = self.request.user.parentguardian
        context['children'] = parent.students.all()
        return context


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
        # Get all parents for selection table (optimized)
        all_parents = ParentGuardian.objects.select_related('user').prefetch_related(
            Prefetch('students', queryset=Student.objects.only('id', 'first_name', 'last_name', 'class_level'))
        ).order_by('user__last_name', 'user__first_name')
        
        # Get statistics for the template
        total_parents = all_parents.count()
        parents_with_email = all_parents.filter(
            Q(email__isnull=False) & ~Q(email='')
        ).count()
        parents_with_phone = all_parents.filter(
            Q(phone_number__isnull=False) & ~Q(phone_number='')
        ).count()
        active_parents = all_parents.filter(
            user__last_login__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # Get recent bulk messages for the sidebar
        recent_messages = ParentMessage.objects.filter(
            sender=request.user,
            is_bulk=True
        ).values('bulk_id', 'subject', 'priority', 'timestamp').annotate(
            count=Count('id'),
            emails_sent=Count('id', filter=Q(email_sent=True)),
            sms_sent=Count('id', filter=Q(sms_sent=True))
        ).order_by('-timestamp')[:5]
        
        # Prepare JSON data for JavaScript
        import json
        all_parents_data = []
        for parent in all_parents:
            communication_channels = parent.get_communication_channels()
            email_channel = next((ch for ch in communication_channels if ch['type'] == 'email'), None)
            sms_channel = next((ch for ch in communication_channels if ch['type'] == 'sms'), None)
            
            all_parents_data.append({
                'id': parent.id,
                'name': parent.get_user_full_name() or 'No Name',
                'students': [
                    {
                        'name': s.get_full_name(), 
                        'class': s.class_level,
                        'class_display': dict(CLASS_LEVEL_CHOICES).get(s.class_level, s.class_level)
                    } 
                    for s in parent.students.all()
                ],
                'email': email_channel['value'] if email_channel else '',
                'phone': sms_channel['value'] if sms_channel else '',
                'email_verified': email_channel['verified'] if email_channel else False,
                'sms_verified': sms_channel['verified'] if sms_channel else False,
                'status': parent.account_status,
                'relationship': parent.get_relationship_display(),
                'last_login': parent.last_login_date.strftime('%Y-%m-%d %H:%M') if parent.last_login_date else 'Never',
                'login_count': parent.login_count,
                'can_login': parent.can_login(),
            })
        
        context = {
            'all_parents': all_parents,
            'all_parents_json': json.dumps(all_parents_data),
            'classes': CLASS_LEVEL_CHOICES,
            'CLASS_LEVEL_CHOICES_JSON': json.dumps(list(CLASS_LEVEL_CHOICES)),
            'target_types': [
                ('ALL', 'All Parents'),
                ('CLASS', 'Specific Class'),
                ('SELECTED', 'Selected Parents'),
                ('OVERDUE_FEES', 'Parents with Overdue Fees'),
                ('LOW_ATTENDANCE', 'Parents of Students with Low Attendance'),
                ('POOR_GRADES', 'Parents of Students with Poor Grades'),
                ('INACTIVE', 'Inactive Parents (No login in 30 days)'),
                ('PENDING', 'Parents with Pending Accounts'),
            ],
            'priority_choices': ParentMessage.PRIORITY_CHOICES,
            'total_parents': total_parents,
            'parents_with_email': parents_with_email,
            'parents_with_phone': parents_with_phone,
            'active_parents': active_parents,
            'recent_messages': recent_messages,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        target_type = request.POST.get('target_type')
        target_class = request.POST.get('target_class')
        selected_parents = request.POST.getlist('selected_parents')
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        priority = request.POST.get('priority', 'normal')
        send_email = request.POST.get('send_email') == 'on'
        send_sms = request.POST.get('send_sms') == 'on'
        include_in_app = request.POST.get('include_in_app', 'on') == 'on'
        
        # Validation
        errors = []
        if not subject:
            errors.append('Subject is required')
        elif len(subject) > 200:
            errors.append('Subject must be less than 200 characters')
        
        if not message:
            errors.append('Message is required')
        
        if not include_in_app and not send_email and not send_sms:
            errors.append('At least one delivery method must be selected')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return self.get(request)
        
        # Get target parents based on selection
        parents = self._get_target_parents(target_type, target_class, selected_parents, request.user)
        
        if not parents:
            messages.error(request, 'No parents found matching your criteria')
            return self.get(request)
        
        # Generate bulk ID
        bulk_id = f"bulk_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Track statistics
        stats = {
            'total': len(parents),
            'success': 0,
            'failed': 0,
            'email_sent': 0,
            'sms_sent': 0,
            'in_app_sent': 0,
            'failed_parents': []
        }
        
        # Process each parent
        for parent in parents:
            try:
                with transaction.atomic():
                    # Check if parent has user account
                    if not parent.user:
                        stats['failed'] += 1
                        stats['failed_parents'].append({
                            'name': parent.get_user_full_name() or f"Parent ID: {parent.id}",
                            'reason': 'No user account'
                        })
                        continue
                    
                    # Create message if in-app notification is enabled
                    if include_in_app:
                        parent_message = ParentMessage.create_bulk_message(
                            sender=request.user,
                            parent=parent,
                            subject=subject,
                            message=message,
                            bulk_id=bulk_id,
                            priority=priority
                        )
                        stats['in_app_sent'] += 1
                    else:
                        parent_message = None
                    
                    # Send email if requested and parent has email
                    if send_email and parent.email and parent.has_valid_phone():
                        try:
                            self._send_email_notification(parent, subject, message, request.user, parent_message)
                            stats['email_sent'] += 1
                        except Exception as e:
                            logger.error(f"Failed to send email to {parent.email}: {str(e)}")
                    
                    # Send SMS if requested and parent has valid phone
                    if send_sms and parent.phone_number and parent.has_valid_phone():
                        try:
                            self._send_sms_notification(parent, subject, message, request.user, parent_message)
                            stats['sms_sent'] += 1
                        except Exception as e:
                            logger.error(f"Failed to send SMS to {parent.phone_number}: {str(e)}")
                    
                    stats['success'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to process parent {parent.id}: {str(e)}")
                stats['failed'] += 1
                stats['failed_parents'].append({
                    'name': parent.get_user_full_name() or f"Parent ID: {parent.id}",
                    'reason': str(e)[:100]
                })
        
        # Show success/failure messages
        success_msg = self._format_success_message(stats)
        
        if stats['success'] > 0:
            messages.success(request, success_msg)
        else:
            messages.error(request, 'Failed to send messages to any parents')
        
        # Store detailed stats in session for display
        request.session['bulk_message_stats'] = {
            'stats': stats,
            'subject': subject,
            'timestamp': timezone.now().isoformat(),
            'target_type': target_type,
            'bulk_id': bulk_id
        }
        
        # Log the bulk message for audit
        self._log_bulk_message(request.user, target_type, stats, subject, bulk_id)
        
        return redirect('parent_bulk_message_results')
    
    def _get_target_parents(self, target_type, target_class, selected_parents, user):
        """Get parents based on target criteria"""
        parents = ParentGuardian.objects.all()
        
        if target_type == 'ALL':
            return parents
        
        elif target_type == 'CLASS' and target_class:
            return parents.filter(students__class_level=target_class).distinct()
        
        elif target_type == 'SELECTED' and selected_parents:
            return parents.filter(id__in=selected_parents)
        
        elif target_type == 'OVERDUE_FEES':
            # Get parents with students who have overdue fees
            from core.models import Fee
            overdue_fee_students = Fee.objects.filter(
                payment_status__in=['UNPAID', 'PARTIAL'],
                due_date__lt=timezone.now().date()
            ).values_list('student_id', flat=True)
            return parents.filter(students__id__in=overdue_fee_students).distinct()
        
        elif target_type == 'LOW_ATTENDANCE':
            # Get parents with students with low attendance (< 70%) in current month
            from core.models import StudentAttendance
            current_month = timezone.now().month
            current_year = timezone.now().year
            
            # Get student attendance stats
            attendance_stats = StudentAttendance.objects.filter(
                date__month=current_month,
                date__year=current_year
            ).values('student').annotate(
                present=Count('id', filter=Q(status='present')),
                total=Count('id')
            )
            
            low_attendance_students = []
            for stat in attendance_stats:
                if stat['total'] > 0 and (stat['present'] / stat['total']) < 0.7:
                    low_attendance_students.append(stat['student'])
            
            return parents.filter(students__id__in=low_attendance_students).distinct()
        
        elif target_type == 'POOR_GRADES':
            # Get parents with students with average grade < 50%
            from core.models import Grade
            from django.db.models import Avg
            
            # Get students with poor grades (average < 50)
            poor_grade_students = Grade.objects.values('student').annotate(
                avg_score=Avg('total_score')
            ).filter(avg_score__lt=50).values_list('student_id', flat=True)
            
            return parents.filter(students__id__in=poor_grade_students).distinct()
        
        elif target_type == 'INACTIVE':
            # Parents who haven't logged in for 30 days
            return parents.filter(
                user__last_login__lt=timezone.now() - timedelta(days=30)
            )
        
        elif target_type == 'PENDING':
            # Parents with pending accounts
            return parents.filter(account_status='pending')
        
        return ParentGuardian.objects.none()
    
    def _send_email_notification(self, parent, subject, message, sender, parent_message=None):
        """Send email notification to parent"""
        try:
            # This is a placeholder - implement your email sending logic
            # Example using Django send_mail:
            from django.core.mail import send_mail
            send_mail(
                subject=f"[School] {subject}",
                message=f"{message}\n\n---\nThis message was sent by {sender.get_full_name()}",
                from_email='school@example.com',
                recipient_list=[parent.email],
                fail_silently=False,
            )

            # If we have a parent_message object, mark email as sent
            if parent_message:
                parent_message.mark_email_sent()
            
            logger.info(f"Email sent to {parent.email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {parent.email}: {str(e)}")
            return False
    
    def _send_sms_notification(self, parent, subject, message, sender, parent_message=None):
        """Send SMS notification to parent"""
        try:
            # This is a placeholder - implement your SMS sending logic
            # Ensure phone number is valid
            if not parent.has_valid_phone():
                logger.warning(f"Invalid phone number for parent {parent.id}: {parent.phone_number}")
                return False
            
            # Truncate message for SMS (160 characters max)
            sms_message = f"{subject}: {message[:140]}..." if len(message) > 140 else f"{subject}: {message}"
            
            # Example using an SMS gateway API:
            # sms_gateway.send_sms(parent.phone_number, sms_message)
            
            # If we have a parent_message object, mark SMS as sent
            if parent_message:
                parent_message.mark_sms_sent()
            
            logger.info(f"SMS sent to {parent.phone_number}: {sms_message[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS to {parent.phone_number}: {str(e)}")
            return False
    
    def _format_success_message(self, stats):
        """Format success message with statistics"""
        parts = []
        
        if stats['success'] > 0:
            parts.append(f"Successfully processed {stats['success']} parents")
        
        delivery_methods = []
        if stats['in_app_sent'] > 0:
            delivery_methods.append(f"{stats['in_app_sent']} in-app")
        if stats['email_sent'] > 0:
            delivery_methods.append(f"{stats['email_sent']} email")
        if stats['sms_sent'] > 0:
            delivery_methods.append(f"{stats['sms_sent']} SMS")
        
        if delivery_methods:
            parts.append(f"via {', '.join(delivery_methods)}")
        
        if stats['failed'] > 0:
            parts.append(f"(Failed: {stats['failed']})")
        
        return " ".join(parts)
    
    def _log_bulk_message(self, user, target_type, stats, subject, bulk_id):
        """Log bulk message for audit purposes"""
        from core.models import AuditLog
        
        try:
            AuditLog.objects.create(
                user=user,
                action='BULK_MSG',  # Use shorter code (8 chars) to fit max_length=10
                model_name='ParentMessage',
                object_id=bulk_id,
                details={
                    'target_type': target_type,
                    'bulk_id': bulk_id,
                    'subject': subject[:100],
                    'stats': stats,
                    'timestamp': timezone.now().isoformat(),
                },
                ip_address=self.request.META.get('REMOTE_ADDR', ''),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )
        except Exception as e:
            logger.error(f"Failed to log bulk message: {str(e)}")


class BulkMessageResultsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Display results of a bulk message send"""
    template_name = 'core/parents/bulk_message_results.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get stats from session
        stats_data = self.request.session.pop('bulk_message_stats', None)
        
        if not stats_data:
            messages.error(self.request, 'No bulk message results found')
            return context
        
        context.update({
            'stats': stats_data['stats'],
            'subject': stats_data['subject'],
            'timestamp': stats_data['timestamp'],
            'target_type': stats_data['target_type'],
            'bulk_id': stats_data['bulk_id'],
        })
        
        # Get messages from this bulk send
        if stats_data.get('bulk_id'):
            context['messages'] = ParentMessage.get_bulk_messages(stats_data['bulk_id']).select_related(
                'parent', 'receiver'
            )[:50]  # Limit to 50 for display
        
        return context


class ParentMessageAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Analytics view for parent messages"""
    template_name = 'core/parents/message_analytics.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Time ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Get messages sent by current user
        all_messages = ParentMessage.objects.filter(sender=self.request.user)
        
        # Message statistics
        context['total_messages'] = all_messages.count()
        context['bulk_messages'] = all_messages.filter(is_bulk=True).count()
        context['individual_messages'] = context['total_messages'] - context['bulk_messages']
        
        # Read rate
        read_messages = all_messages.filter(is_read=True).count()
        context['read_rate'] = round((read_messages / context['total_messages'] * 100), 1) if context['total_messages'] > 0 else 0
        
        # Delivery statistics
        context['email_sent_count'] = all_messages.filter(email_sent=True).count()
        context['sms_sent_count'] = all_messages.filter(sms_sent=True).count()
        
        # Recent activity
        context['recent_week_messages'] = all_messages.filter(
            timestamp__gte=week_ago
        ).count()
        
        context['recent_month_messages'] = all_messages.filter(
            timestamp__gte=month_ago
        ).count()
        
        # Priority distribution
        priority_distribution = all_messages.values('priority').annotate(
            count=Count('id')
        ).order_by('priority')
        context['priority_distribution'] = list(priority_distribution)
        
        # Bulk message performance
        bulk_messages = all_messages.filter(is_bulk=True).values('bulk_id').annotate(
            count=Count('id'),
            read_count=Count('id', filter=Q(is_read=True)),
            email_count=Count('id', filter=Q(email_sent=True)),
            sms_count=Count('id', filter=Q(sms_sent=True))
        ).order_by('-count')[:10]
        
        context['top_bulk_messages'] = bulk_messages
        
        # Response rate (messages from parents to this user)
        responses = ParentMessage.objects.filter(
            receiver=self.request.user,
            sender__parentguardian__isnull=False
        ).count()
        
        context['response_rate'] = round((responses / context['total_messages'] * 100), 1) if context['total_messages'] > 0 else 0
        
        return context


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