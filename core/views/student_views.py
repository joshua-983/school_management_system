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
        try:
            self.object = self.get_object()
            student_id = self.object.student_id
            student_name = self.object.get_full_name()
            
            print(f"Starting deletion process for student: {student_name} ({student_id})")
            
            # USE RAW SQL TO BYPASS ALL DATABASE SCHEMA ISSUES
            from django.db import connection
            
            with connection.cursor() as cursor:
                student_id_param = [self.object.id]
                
                # DELETE IN CORRECT ORDER TO RESPECT FOREIGN KEY CONSTRAINTS
                
                # 1. First delete FeePayment records (they depend on Fee and Bill)
                cursor.execute("DELETE FROM core_feepayment WHERE fee_id IN (SELECT id FROM core_fee WHERE student_id = %s)", student_id_param)
                cursor.execute("DELETE FROM core_feepayment WHERE bill_id IN (SELECT id FROM core_bill WHERE student_id = %s)", student_id_param)
                print("✅ Deleted FeePayment records")
                
                # 2. Delete BillPayment records (they depend on Bill)
                cursor.execute("DELETE FROM core_billpayment WHERE bill_id IN (SELECT id FROM core_bill WHERE student_id = %s)", student_id_param)
                print("✅ Deleted BillPayment records")
                
                # 3. Delete BillItem records (they depend on Bill)
                cursor.execute("DELETE FROM core_billitem WHERE bill_id IN (SELECT id FROM core_bill WHERE student_id = %s)", student_id_param)
                print("✅ Deleted BillItem records")
                
                # 4. Delete FeeInstallment records (they depend on Fee)
                cursor.execute("DELETE FROM core_feeinstallment WHERE fee_id IN (SELECT id FROM core_fee WHERE student_id = %s)", student_id_param)
                print("✅ Deleted FeeInstallment records")
                
                # 5. Delete FeeDiscount records
                cursor.execute("DELETE FROM core_feediscount WHERE student_id = %s", student_id_param)
                print("✅ Deleted FeeDiscount records")
                
                # 6. Delete Bill records
                cursor.execute("DELETE FROM core_bill WHERE student_id = %s", student_id_param)
                print("✅ Deleted Bill records")
                
                # 7. Delete Fee records
                cursor.execute("DELETE FROM core_fee WHERE student_id = %s", student_id_param)
                print("✅ Deleted Fee records")
                
                # 8. Delete Grade records
                cursor.execute("DELETE FROM core_grade WHERE student_id = %s", student_id_param)
                print("✅ Deleted Grade records")
                
                # 9. Delete StudentAssignment records
                cursor.execute("DELETE FROM core_studentassignment WHERE student_id = %s", student_id_param)
                print("✅ Deleted StudentAssignment records")
                
                # 10. Delete StudentAttendance records
                cursor.execute("DELETE FROM core_studentattendance WHERE student_id = %s", student_id_param)
                print("✅ Deleted StudentAttendance records")
                
                # 11. Delete many-to-many relationships
                cursor.execute("DELETE FROM core_student_parentguardian WHERE student_id = %s", student_id_param)
                print("✅ Deleted parent relationships")
                
                # 12. Finally delete the student
                cursor.execute("DELETE FROM core_student WHERE id = %s", student_id_param)
                print(f"✅ Successfully deleted student: {student_name} ({student_id})")
            
            messages.success(request, f'Student {student_name} ({student_id}) deleted successfully')
            
        except Exception as e:
            error_msg = f'Error deleting student: {str(e)}'
            print(f"❌ {error_msg}")
            messages.error(request, error_msg)
            return redirect('student_list')
        
        return redirect(self.success_url)


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
        student = self.request.user.student
        return Fee.objects.filter(student=student).select_related('category').order_by('-academic_year', '-term', 'due_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student
        
        # Get all fees for the student
        fees = Fee.objects.filter(student=student)
        
        # Calculate comprehensive fee summary
        fee_summary = fees.aggregate(
            total_payable=Sum('amount_payable') or 0,
            total_paid=Sum('amount_paid') or 0,
            total_balance=Sum('balance') or 0
        )
        
        # Calculate payment status counts
        status_counts = {
            'paid': fees.filter(payment_status='PAID').count(),
            'partial': fees.filter(payment_status='PARTIAL').count(),
            'unpaid': fees.filter(payment_status='UNPAID').count(),
            'overdue': fees.filter(payment_status='OVERDUE').count(),
        }
        
        # Summary by academic year and term
        term_summary = fees.values('academic_year', 'term').annotate(
            payable=Sum('amount_payable') or 0,
            paid=Sum('amount_paid') or 0,
            balance=Sum('balance') or 0,
            count=Count('id')
        ).order_by('-academic_year', '-term')
        
        # Get recent payments
        from ..models import FeePayment
        recent_payments = FeePayment.objects.filter(
            fee__student=student
        ).select_related('fee', 'fee__category').order_by('-payment_date')[:5]
        
        context.update({
            'fee_summary': fee_summary,
            'term_summary': term_summary,
            'status_counts': status_counts,
            'recent_payments': recent_payments,
            'student': student,
            'total_fees': fees.count(),
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
        context['completion_rate'] = round((completed_count / total_assignments * 100), 1) if total_assignments > 0 else 0
        
        # Assignment counts for dashboard
        pending_assignments = len([a for a in assignments if a.status in ['PENDING', 'LATE']])
        submitted_assignments = len([a for a in assignments if a.status in ['SUBMITTED', 'GRADED']])
        graded_assignments = len([a for a in assignments if a.status == 'GRADED'])
        due_soon_assignments = len(context['due_soon_assignments'])
        
        # IMPROVED FEE SECTION - Comprehensive fee data
        fees = Fee.objects.filter(student=student).select_related('category')
        
        # Calculate fee totals with proper handling of None values
        fee_aggregates = fees.aggregate(
            total_payable=Sum('amount_payable'),
            total_paid=Sum('amount_paid'),
            total_balance=Sum('balance')
        )
        
        total_payable = fee_aggregates['total_payable'] or 0
        total_paid = fee_aggregates['total_paid'] or 0
        total_balance = total_payable - total_paid
        
        # More accurate fee status calculation
        if total_balance <= 0 and fees.exists():
            fee_status = 'PAID'
            fee_status_class = 'success'
            fee_status_icon = 'bi-check-circle'
            fee_message = 'All fees are paid'
        elif total_paid > 0:
            fee_status = 'PARTIAL'
            fee_status_class = 'warning'
            fee_status_icon = 'bi-exclamation-circle'
            fee_message = f'GH₵{total_balance} balance remaining'
        else:
            fee_status = 'UNPAID'
            fee_status_class = 'danger'
            fee_status_icon = 'bi-x-circle'
            fee_message = 'No payments made yet'
        
        # Check for overdue fees
        overdue_fees = fees.filter(
            due_date__lt=timezone.now().date(),
            payment_status__in=['UNPAID', 'PARTIAL', 'OVERDUE']
        ).exists()
        
        # Get fee status breakdown
        fee_status_counts = {
            'paid': fees.filter(payment_status='PAID').count(),
            'partial': fees.filter(payment_status='PARTIAL').count(),
            'unpaid': fees.filter(payment_status='UNPAID').count(),
            'overdue': fees.filter(payment_status='OVERDUE').count(),
            'total': fees.count()
        }
        
        # Get current term fees summary
        current_term_fees = fees.filter(
            academic_year=academic_year,
            term=current_term.term if current_term else 1
        )
        current_term_summary = current_term_fees.aggregate(
            payable=Sum('amount_payable') or 0,
            paid=Sum('amount_paid') or 0,
            balance=Sum('balance') or 0,
            count=Count('id')
        )
        
        # Get recent payments for dashboard
        from ..models import FeePayment
        recent_payments = FeePayment.objects.filter(
            fee__student=student
        ).select_related('fee', 'fee__category').order_by('-payment_date')[:3]
        
        # Comprehensive fee summary for dashboard
        fee_summary = {
            'total_payable': total_payable,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'overdue_count': fees.filter(
                due_date__lt=timezone.now().date(),
                payment_status__in=['UNPAID', 'PARTIAL']
            ).count(),
            'paid_count': fees.filter(payment_status='PAID').count(),
            'partial_count': fees.filter(payment_status='PARTIAL').count(),
            'unpaid_count': fees.filter(payment_status='UNPAID').count(),
            'status': fee_status,
            'status_class': fee_status_class,
            'status_icon': fee_status_icon,
            'message': fee_message,
            'has_fees': fees.exists(),
        }
        
        # Calculate average grade for current term
        current_grades = Grade.objects.filter(
            student=student,
            academic_year=academic_year,
            term=current_term.term if current_term else 1
        )
        average_grade = current_grades.aggregate(Avg('total_score'))['total_score__avg'] or 0
        
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
        
        # Calculate attendance percentage
        total_attendance = attendance_summary['total'] or 0
        present_count = attendance_summary['present'] or 0
        attendance_percentage = round((present_count / total_attendance * 100), 1) if total_attendance > 0 else 0
        
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
        
        # Update context with all data
        context.update({
            'student': student,
            
            # Assignment data
            'assignments': assignments,
            'pending_assignments': pending_assignments,
            'submitted_assignments': submitted_assignments,
            'graded_assignments': graded_assignments,
            'due_soon': due_soon_assignments,
            'completion_rate': context['completion_rate'],
            
            # Grade data
            'average_grade': round(average_grade, 1),
            'recent_grades': recent_grades,
            
            # IMPROVED FEE DATA - Comprehensive fee information
            'fee_status': fee_status,
            'fee_status_class': fee_status_class,
            'fee_status_icon': fee_status_icon,
            'fee_message': fee_message,
            'total_balance': total_balance,
            'overdue_fees': overdue_fees,
            'fee_summary': fee_summary,
            'fee_status_counts': fee_status_counts,
            'current_term_summary': current_term_summary,
            'recent_payments': recent_payments,
            'total_fees': fees.count(),
            
            # Attendance data
            'attendance_summary': attendance_summary,
            'attendance_percentage': attendance_percentage,
            
            # Timetable data
            'today_timetable': today_timetable,
            
            # System data
            'current_academic_year': academic_year,
            'current_term': current_term,
            'today': timezone.now().date(),
            'now': timezone.now(),
        })
        
        return context