from django.db.models import Q, Count, Avg, Sum
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from datetime import timedelta

from .base_views import *
from ..forms import StudentProfileForm, StudentRegistrationForm
from ..models import Student, ClassAssignment, StudentAttendance, Fee, Grade, AcademicTerm, StudentAssignment, Timetable


CLASS_LEVEL_CHOICES = [
    ('P1', 'Primary 1'),
    ('P2', 'Primary 2'),
    ('P3', 'Primary 3'),
    ('P4', 'Primary 4'),
    ('P5', 'Primary 5'),
    ('P6', 'Primary 6'),
    ('J1', 'JHS 1'),
    ('J2', 'JHS 2'),
    ('J3', 'JHS 3'),
]

@method_decorator(cache_page(60*15), name='dispatch')
class StudentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Student
    template_name = 'core/students/student_list.html'
    context_object_name = 'students'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        class_level = self.request.GET.get('class_level')
        if class_level:
            queryset = queryset.filter(class_level=class_level)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['class_levels'] = CLASS_LEVEL_CHOICES
        
        # Calculate statistics
        queryset = self.get_queryset()
        
        # Total students count
        context['total_students'] = queryset.count()
        
        # Gender counts
        context['male_count'] = queryset.filter(gender='M').count()
        context['female_count'] = queryset.filter(gender='F').count()
        
        # Count distinct active classes
        context['class_count'] = queryset.values('class_level').distinct().count()
        
        # Class distribution for chart (optional)
        class_distribution = queryset.values('class_level').annotate(
            count=Count('id')
        ).order_by('class_level')
        context['class_distribution'] = {
            item['class_level']: item['count'] for item in class_distribution
        }
        
        return context

class StudentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Student
    template_name = 'core/students/student_detail.html'
    context_object_name = 'student'
    
    def test_func(self):
        if is_admin(self.request.user):
            return True
        elif is_teacher(self.request.user):
            student = self.get_object()
            return ClassAssignment.objects.filter(
                class_level=student.class_level,
                teacher=self.request.user.teacher
            ).exists()
        elif is_student(self.request.user):
            return self.request.user.student == self.get_object()
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()
        context['present_count'] = student.attendances.filter(status='present').count()
        context['absent_count'] = student.attendances.filter(status='absent').count()
        context['total_count'] = student.attendances.count()
        return context

class StudentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Student
    form_class = StudentRegistrationForm
    template_name = 'core/students/student_form.html'
    success_url = reverse_lazy('student_list')
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Student created successfully')
        return super().form_valid(form)

class StudentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Student
    form_class = StudentRegistrationForm
    template_name = 'core/students/student_form.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('student_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Student updated successfully')
        return super().form_valid(form)

class StudentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Student
    template_name = 'core/students/student_confirm_delete.html'
    success_url = reverse_lazy('student_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Student deleted successfully')
        return super().delete(request, *args, **kwargs)


# student profile view
class StudentProfileView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Student
    form_class = StudentProfileForm  # You'll need to create this form
    template_name = 'core/students/student_profile.html'
    
    def test_func(self):
        return self.get_object().user == self.request.user
    
    def get_object(self):
        return self.request.user.student
    
    def get_success_url(self):
        messages.success(self.request, 'Profile updated successfully')
        return reverse_lazy('student_profile')

class StudentGradeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Grade
    template_name = 'core/students/student_grades.html'
    context_object_name = 'grades'
    
    def test_func(self):
        return is_student(self.request.user)
    
    def get_queryset(self):
        return Grade.objects.filter(student=self.request.user.student).order_by('-academic_year', '-term', 'subject')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add summary statistics
        grades = self.get_queryset()
        context['grade_summary'] = grades.values('academic_year', 'term').annotate(
            average=Avg('total_score')
        ).order_by('-academic_year', '-term')
        return context

class StudentAttendanceView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = StudentAttendance
    template_name = 'core/students/student_attendance.html'
    context_object_name = 'attendances'
    paginate_by = 20  # Add pagination
    
    def test_func(self):
        return is_student(self.request.user)
    
    def get_queryset(self):
        return StudentAttendance.objects.filter(
            student=self.request.user.student
        ).select_related('term', 'period').order_by('-date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attendances = self.get_queryset()
        
        # Calculate attendance statistics
        attendance_stats = attendances.aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late'))
        )
        
        # Calculate percentages for the stats
        total = attendance_stats['total'] or 1  # Avoid division by zero
        attendance_stats['present_percentage'] = round((attendance_stats['present'] / total) * 100)
        attendance_stats['absent_percentage'] = round((attendance_stats['absent'] / total) * 100)
        attendance_stats['late_percentage'] = round((attendance_stats['late'] / total) * 100)
        
        context['attendance_stats'] = attendance_stats
        
        # Monthly attendance summary
        from django.db.models.functions import TruncMonth
        monthly_summary = attendances.annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            present=Count('id', filter=Q(status='present')),
            total=Count('id')
        ).order_by('-month')[:6]  # Last 6 months
        
        # Calculate percentages for monthly summary
        for month in monthly_summary:
            month_total = month['total'] or 1
            month['present_percentage'] = round((month['present'] / month_total) * 100)
        
        context['monthly_summary'] = monthly_summary
        
        # Add academic terms for the filter dropdown
        from ..models import AcademicTerm
        context['academic_terms'] = AcademicTerm.objects.all().order_by('-start_date')
        
        # Calculate current streak (simplified implementation)
        context['current_streak'] = self.calculate_current_streak(attendances)
        
        return context
    
    def calculate_current_streak(self, attendances):
        """Calculate the current consecutive days present streak"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Get recent attendance records (last 30 days)
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        recent_attendances = attendances.filter(
            date__gte=thirty_days_ago
        ).order_by('-date')
        
        streak = 0
        current_date = timezone.now().date()
        
        # Check consecutive days from today backwards
        for i in range(30):  # Check up to 30 days back
            check_date = current_date - timedelta(days=i)
            day_attendance = recent_attendances.filter(date=check_date).first()
            
            if day_attendance and day_attendance.status == 'present':
                streak += 1
            else:
                break  # Streak broken
        
        return streak

class StudentFeeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Fee
    template_name = 'core/students/student_fees.html'
    context_object_name = 'fees'
    
    def test_func(self):
        return is_student(self.request.user)
    
    def get_queryset(self):
        return Fee.objects.filter(student=self.request.user.student).order_by('-academic_year', '-term')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student
        fees = self.get_queryset()
        
        # Calculate fee summary
        fee_summary = fees.aggregate(
            total_payable=Sum('amount_payable'),
            total_paid=Sum('amount_paid'),
            total_balance=Sum('balance')
        )
        
        # Summary by academic year and term
        term_summary = fees.values('academic_year', 'term').annotate(
            payable=Sum('amount_payable'),
            paid=Sum('amount_paid'),
            balance=Sum('balance')
        ).order_by('-academic_year', '-term')
        
        context.update({
            'fee_summary': fee_summary,
            'term_summary': term_summary,
            'student': student
        })
        
        return context


class StudentDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/students/student_dashboard.html'
    
    def test_func(self):
        return is_student(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student
        
        # Get current academic year and term
        current_year = timezone.now().year
        academic_year = f"{current_year}/{current_year + 1}"
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        
        # ENHANCED: Get assignments with better organization
        assignments = StudentAssignment.objects.filter(
            student=student
        ).select_related(
            'assignment', 
            'assignment__subject',
            'assignment__class_assignment'
        ).order_by('assignment__due_date')
        
        # ENHANCED: Categorize assignments for better UX
        today = timezone.now()
        context['overdue_assignments'] = [
            sa for sa in assignments 
            if sa.assignment.due_date < today and sa.status in ['PENDING', 'LATE']
        ]
        
        context['due_soon_assignments'] = [
            sa for sa in assignments 
            if sa.assignment.due_date <= today + timedelta(days=3) 
            and sa.status in ['PENDING', 'LATE']
            and sa.assignment.due_date >= today
        ]
        
        context['upcoming_assignments'] = [
            sa for sa in assignments 
            if sa.assignment.due_date > today + timedelta(days=3)
            and sa.status in ['PENDING', 'LATE']
        ]
        
        context['completed_assignments'] = [
            sa for sa in assignments 
            if sa.status in ['SUBMITTED', 'GRADED']
        ]
        
        # Progress statistics
        total_assignments = assignments.count()
        completed_count = len(context['completed_assignments'])
        context['completion_rate'] = (completed_count / total_assignments * 100) if total_assignments > 0 else 0
        
        # KEEP ALL YOUR EXISTING CONTEXT DATA:
        # Calculate statistics
        pending_assignments = len([a for a in assignments if a.status in ['PENDING', 'LATE']])
        submitted_assignments = len([a for a in assignments if a.status in ['SUBMITTED', 'GRADED']])
        graded_assignments = len([a for a in assignments if a.status == 'GRADED'])
        due_soon_assignments = len(context['due_soon_assignments'])
        
        # Calculate average grade for current term
        current_grades = Grade.objects.filter(
            student=student,
            academic_year=academic_year,
            term=current_term.term if current_term else 1
        )
        average_grade = current_grades.aggregate(Avg('total_score'))['total_score__avg'] or 0
        
        # Get fee status
        fees = Fee.objects.filter(student=student)
        total_payable = fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0
        total_paid = fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        total_balance = total_payable - total_paid
        
        if total_balance <= 0:
            fee_status = 'PAID'
        elif total_paid > 0:
            fee_status = 'PARTIAL'
        else:
            fee_status = 'UNPAID'
        
        overdue_fees = fees.filter(
            due_date__lt=timezone.now().date(),
            payment_status__in=['unpaid', 'partial']
        ).exists()
        
        # Get recent grades
        recent_grades = Grade.objects.filter(
            student=student
        ).select_related('subject').order_by('-last_updated')[:5]
        
        # Get attendance summary for current month
        current_month = timezone.now().month
        current_year_attendance = timezone.now().year
        
        attendance_summary = StudentAttendance.objects.filter(
            student=student,
            date__month=current_month,
            date__year=current_year_attendance
        ).aggregate(
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            total=Count('id')
        )
        
        # Get today's timetable
        today_weekday = timezone.now().weekday()
        today_timetable = Timetable.objects.filter(
            class_level=student.class_level,
            day_of_week=today_weekday,
            is_active=True
        ).prefetch_related(
            'entries__time_slot',
            'entries__subject',
            'entries__teacher'
        ).first()
        
        context.update({
            'student': student,
            'assignments': assignments,  # Keep original for backward compatibility if needed
            'pending_assignments': pending_assignments,
            'submitted_assignments': submitted_assignments,
            'graded_assignments': graded_assignments,
            'due_soon': due_soon_assignments,
            'average_grade': round(average_grade, 1),
            'fee_status': fee_status,
            'total_balance': total_balance,
            'overdue_fees': overdue_fees,
            'recent_grades': recent_grades,
            'attendance_summary': attendance_summary,
            'today_timetable': today_timetable,
            'current_academic_year': academic_year,
            'current_term': current_term,
            'today': timezone.now().date(),
            'now': timezone.now(),
        })
        
        return context