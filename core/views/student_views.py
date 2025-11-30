from django.db.models import Q, Count, Avg, Sum
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, FormView
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
import logging

from .base_views import *
from ..forms import StudentProfileForm, StudentRegistrationForm, StudentParentAssignmentForm
from ..models import Student, ClassAssignment, StudentAttendance, Fee, Grade, AcademicTerm, StudentAssignment, Timetable, FeePayment, Bill, BillPayment, BillItem, FeeInstallment, FeeDiscount

logger = logging.getLogger(__name__)

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

class StudentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Student
    template_name = 'core/students/student_list.html'
    context_object_name = 'students'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_queryset(self):
        # Get ALL students without any caching for debugging
        queryset = Student.objects.all()
        
        class_level = self.request.GET.get('class_level')
        if class_level:
            queryset = queryset.filter(class_level=class_level)
        
        # DEBUG: Print detailed student information
        print(f"🔍 [STUDENT LIST DEBUG] Total students in database: {queryset.count()}")
        students_info = list(queryset.values_list('id', 'student_id', 'first_name', 'last_name', 'class_level', 'is_active'))
        print(f"🔍 [STUDENT LIST DEBUG] Students in queryset: {students_info}")
        
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
        
        # DEBUG: Print context data
        print(f"🔍 [STUDENT LIST DEBUG] Context total_students: {context['total_students']}")
        print(f"🔍 [STUDENT LIST DEBUG] Students in context: {list(context['students'].values_list('id', 'student_id'))}")
        
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
        
        # Attendance statistics
        context['present_count'] = student.attendances.filter(status='present').count()
        context['absent_count'] = student.attendances.filter(status='absent').count()
        context['total_count'] = student.attendances.count()
        
        # Parent information
        context['parents'] = student.parents.all().select_related('user')
        context['parent_form'] = StudentParentAssignmentForm(student=self.object)
        context['can_manage_parents'] = is_admin(self.request.user)
        
        # Parent statistics
        context['parents_with_accounts'] = student.parents.filter(user__isnull=False).count()
        context['active_parents'] = student.parents.filter(account_status='active').count()
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle parent management actions"""
        if not is_admin(request.user):
            raise PermissionDenied("Only admins can manage parents")
        
        self.object = self.get_object()
        action = request.POST.get('action')
        
        if action == 'add_parent':
            return self.add_parent(request)
        elif action == 'remove_parent':
            return self.remove_parent(request)
        elif action == 'create_parent':
            return self.create_parent(request)
        
        messages.error(request, 'Invalid action')
        return redirect('student_detail', pk=self.object.pk)
    
    def add_parent(self, request):
        """Add existing parent to student"""
        parent_id = request.POST.get('parent_id')
        try:
            parent = ParentGuardian.objects.get(pk=parent_id)
            self.object.parents.add(parent)
            messages.success(request, f'Added {parent.get_user_full_name()} as parent')
        except ParentGuardian.DoesNotExist:
            messages.error(request, 'Parent not found')
        
        return redirect('student_detail', pk=self.object.pk)
    
    def remove_parent(self, request):
        """Remove parent from student"""
        parent_id = request.POST.get('parent_id')
        try:
            parent = ParentGuardian.objects.get(pk=parent_id)
            self.object.parents.remove(parent)
            messages.success(request, f'Removed {parent.get_user_full_name()} from parents')
        except ParentGuardian.DoesNotExist:
            messages.error(request, 'Parent not found')
        
        return redirect('student_detail', pk=self.object.pk)
    
    def create_parent(self, request):
        """Create new parent for student"""
        form = StudentParentAssignmentForm(request.POST, student=self.object)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Parent created and linked successfully')
            except Exception as e:
                messages.error(request, f'Error creating parent: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors in the form')
        
        return redirect('student_detail', pk=self.object.pk)

class StudentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Student
    form_class = StudentRegistrationForm
    template_name = 'core/students/student_form.html'
    success_url = reverse_lazy('student_list')
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_form_kwargs(self):
        """Add request to form kwargs for parent creation"""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def get_context_data(self, **kwargs):
        """Add parent statistics to context"""
        context = super().get_context_data(**kwargs)
        # Add parent statistics for the template
        context['total_parents'] = ParentGuardian.objects.count()
        context['active_parents'] = ParentGuardian.objects.filter(account_status='active').count()
        return context
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Save the student first
                self.object = form.save()
                
                # Handle parent creation/linking
                create_parent_account = form.cleaned_data.get('create_parent_account', False)
                selected_parents = form.cleaned_data.get('parents', [])
                
                # Link selected existing parents
                if selected_parents:
                    self.object.parents.set(selected_parents)
                    messages.info(self.request, f'Linked {len(selected_parents)} existing parents to student')
                
                # Create new parent account if requested
                if create_parent_account:
                    self.create_parent_from_student(form)
                
                messages.success(self.request, f'Student {self.object.get_full_name()} created successfully!')
                return redirect(self.get_success_url())
                
        except Exception as e:
            messages.error(self.request, f'Error creating student: {str(e)}')
            return self.form_invalid(form)
    
    def create_parent_from_student(self, form):
        """Create a parent account based on student information"""
        try:
            student = self.object
            
            # Generate parent email if not provided in form
            parent_email = form.cleaned_data.get('parent_email')
            if not parent_email:
                parent_email = f"parent.{student.student_id}@school.edu.gh"
            
            # Generate parent phone if not provided
            parent_phone = form.cleaned_data.get('parent_phone')
            if not parent_phone:
                parent_phone = "0240000000"  # Default placeholder
            
            # Create parent record
            parent = ParentGuardian.objects.create(
                relationship=form.cleaned_data.get('parent_relationship', 'G'),
                email=parent_email,
                phone_number=parent_phone,
                account_status='pending'
            )
            
            # Link parent to student
            parent.students.add(student)
            
            # Create user account for parent
            if parent_email and parent_email != "parent.{student.student_id}@school.edu.gh":
                try:
                    parent.create_user_account()
                    messages.info(self.request, f'Created parent account for {parent_email}')
                except Exception as e:
                    messages.warning(self.request, f'Could not create user account for parent: {str(e)}')
            
            messages.success(self.request, 'Parent account created successfully')
            
        except Exception as e:
            messages.error(self.request, f'Error creating parent account: {str(e)}')
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

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
    
    def get_object(self, queryset=None):
        """Override to handle already deleted students"""
        try:
            obj = super().get_object(queryset)
            print(f"🔍 [DELETE DEBUG] StudentDeleteView.get_object() - Found student: ID={obj.id}, Name={obj.get_full_name()}, StudentID={obj.student_id}")
            return obj
        except Student.DoesNotExist:
            print(f"🔍 [DELETE DEBUG] StudentDeleteView.get_object() - Student with pk={self.kwargs.get('pk')} does not exist")
            return None
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests for delete confirmation"""
        print(f"🔍 [DELETE DEBUG] StudentDeleteView.get() - Processing GET request for student deletion")
        self.object = self.get_object()
        if self.object is None:
            messages.error(request, 'Student not found or already deleted.')
            return redirect('student_list')
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)
    
    def delete(self, request, *args, **kwargs):
        print(f"🔍 [DELETE DEBUG] StudentDeleteView.delete() - Starting deletion process")
        
        try:
            self.object = self.get_object()
            
            # If student doesn't exist, just redirect
            if self.object is None:
                print(f"🔍 [DELETE DEBUG] Student object is None - student already deleted")
                messages.info(request, 'Student was already deleted.')
                return redirect('student_list')
            
            student_id = self.object.student_id
            student_name = self.object.get_full_name()
            student_db_id = self.object.id
            
            print(f"🚀 [DELETE DEBUG] Starting safe deletion process for student:")
            print(f"   - Database ID: {student_db_id}")
            print(f"   - Student ID: {student_id}")
            print(f"   - Name: {student_name}")
            
            # Verify student exists in database before starting deletion
            pre_deletion_check = Student.objects.filter(id=student_db_id).exists()
            print(f"🔍 [DELETE DEBUG] Pre-deletion database check - Student exists: {pre_deletion_check}")
            
            if not pre_deletion_check:
                messages.error(request, 'Student not found in database.')
                return redirect('student_list')
            
            # Use Django ORM with transaction safety
            with transaction.atomic():
                print(f"🔍 [DELETE DEBUG] Transaction started")
                
                # Get all related objects first with counts
                student_fees = Fee.objects.filter(student=self.object)
                student_bills = Bill.objects.filter(student=self.object)
                student_grades = Grade.objects.filter(student=self.object)
                student_assignments = StudentAssignment.objects.filter(student=self.object)
                student_attendance = StudentAttendance.objects.filter(student=self.object)
                student_discounts = FeeDiscount.objects.filter(student=self.object)
                
                print(f"🔍 [DELETE DEBUG] Related records found:")
                print(f"   - Fees: {student_fees.count()}")
                print(f"   - Bills: {student_bills.count()}")
                print(f"   - Grades: {student_grades.count()}")
                print(f"   - Assignments: {student_assignments.count()}")
                print(f"   - Attendance: {student_attendance.count()}")
                print(f"   - Discounts: {student_discounts.count()}")
                
                # Delete in proper order to respect foreign key constraints
                
                # 1. Delete FeePayment records
                fee_payments = FeePayment.objects.filter(
                    Q(fee__in=student_fees) | Q(bill__in=student_bills)
                )
                fee_payments_count = fee_payments.count()
                fee_payments.delete()
                print(f"✅ [DELETE DEBUG] Deleted {fee_payments_count} FeePayment records")
                
                # 2. Delete BillPayment records
                bill_payments = BillPayment.objects.filter(bill__in=student_bills)
                bill_payments_count = bill_payments.count()
                bill_payments.delete()
                print(f"✅ [DELETE DEBUG] Deleted {bill_payments_count} BillPayment records")
                
                # 3. Delete BillItem records
                bill_items = BillItem.objects.filter(bill__in=student_bills)
                bill_items_count = bill_items.count()
                bill_items.delete()
                print(f"✅ [DELETE DEBUG] Deleted {bill_items_count} BillItem records")
                
                # 4. Delete FeeInstallment records
                fee_installments = FeeInstallment.objects.filter(fee__in=student_fees)
                fee_installments_count = fee_installments.count()
                fee_installments.delete()
                print(f"✅ [DELETE DEBUG] Deleted {fee_installments_count} FeeInstallment records")
                
                # 5. Delete FeeDiscount records
                fee_discounts_count = student_discounts.count()
                student_discounts.delete()
                print(f"✅ [DELETE DEBUG] Deleted {fee_discounts_count} FeeDiscount records")
                
                # 6. Delete Bill records
                bills_count = student_bills.count()
                student_bills.delete()
                print(f"✅ [DELETE DEBUG] Deleted {bills_count} Bill records")
                
                # 7. Delete Fee records
                fees_count = student_fees.count()
                student_fees.delete()
                print(f"✅ [DELETE DEBUG] Deleted {fees_count} Fee records")
                
                # 8. Delete Grade records
                grades_count = student_grades.count()
                student_grades.delete()
                print(f"✅ [DELETE DEBUG] Deleted {grades_count} Grade records")
                
                # 9. Delete StudentAssignment records
                assignments_count = student_assignments.count()
                student_assignments.delete()
                print(f"✅ [DELETE DEBUG] Deleted {assignments_count} StudentAssignment records")
                
                # 10. Delete StudentAttendance records
                attendance_count = student_attendance.count()
                student_attendance.delete()
                print(f"✅ [DELETE DEBUG] Deleted {attendance_count} StudentAttendance records")
                
                # 11. Clear many-to-many relationships
                parent_count = self.object.parentguardian_set.count()
                self.object.parentguardian_set.clear()
                print(f"✅ [DELETE DEBUG] Cleared {parent_count} parent relationships")
                
                # 12. Finally delete the student
                print(f"🔍 [DELETE DEBUG] About to delete student record...")
                result = super().delete(request, *args, **kwargs)
                print(f"✅ [DELETE DEBUG] Successfully deleted student: {student_name} ({student_id})")
                
                # Verify deletion
                post_deletion_check = Student.objects.filter(id=student_db_id).exists()
                print(f"🔍 [DELETE DEBUG] Post-deletion check - Student still exists: {post_deletion_check}")
                
                if post_deletion_check:
                    print(f"❌ [DELETE DEBUG] Student deletion failed - student still exists in database!")
                    raise Exception("Student deletion failed - record still exists")
                
            print(f"🎉 [DELETE DEBUG] Student deletion completed successfully")
            messages.success(request, f'Student {student_name} ({student_id}) deleted successfully')
            return result
            
        except Exception as e:
            error_msg = f'Error deleting student: {str(e)}'
            print(f"❌ [DELETE DEBUG] {error_msg}")
            import traceback
            print(f"❌ [DELETE DEBUG] Traceback: {traceback.format_exc()}")
            messages.error(request, error_msg)
            return redirect('student_list')


# student profile view
class StudentProfileView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Student
    form_class = StudentProfileForm
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
    paginate_by = 20
    
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
        total = attendance_stats['total'] or 1
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
        ).order_by('-month')[:6]
        
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
        for i in range(30):
            check_date = current_date - timedelta(days=i)
            day_attendance = recent_attendances.filter(date=check_date).first()
            
            if day_attendance and day_attendance.status == 'present':
                streak += 1
            else:
                break
        
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
        
        # DEBUG: Print student information
        print(f"🔍 [DASHBOARD DEBUG] Loading dashboard for student: {student.get_full_name()} (ID: {student.id})")
        
        # Get current academic year and term
        current_year = timezone.now().year
        academic_year = f"{current_year}/{current_year + 1}"
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        
        # Get assignments with better organization
        assignments = StudentAssignment.objects.filter(
            student=student
        ).select_related(
            'assignment', 
            'assignment__subject',
            'assignment__class_assignment'
        ).order_by('assignment__due_date')
        
        # Categorize assignments for better UX
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
        
        # Comprehensive fee data
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
            
            # Fee data
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


class ReportCardFormView(LoginRequiredMixin, TemplateView):
    template_name = 'core/report_card_form.html'
    
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class StudentParentManagementView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """Enhanced view for managing student-parent relationships"""
    template_name = 'core/students/student_parent_management.html'
    form_class = StudentParentAssignmentForm
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['student'] = self.get_student()
        return kwargs
    
    def get_student(self):
        """Get the student object"""
        return get_object_or_404(Student, pk=self.kwargs['pk'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_student()
        
        # Get all parents (for linking existing ones)
        all_parents = ParentGuardian.objects.all().select_related('user')
        
        context.update({
            'student': student,
            'current_parents': student.parents.all().select_related('user'),
            'available_parents': all_parents.exclude(id__in=student.parents.values_list('id', flat=True)),
            'parent_stats': {
                'total': all_parents.count(),
                'with_accounts': all_parents.filter(user__isnull=False).count(),
                'active': all_parents.filter(account_status='active').count(),
            }
        })
        return context
    
    def form_valid(self, form):
        student = self.get_student()
        try:
            with transaction.atomic():
                result = form.save()
                
                if result:
                    messages.success(self.request, f'Parent assignments updated successfully for {student.get_full_name()}')
                else:
                    messages.info(self.request, 'No changes made to parent assignments')
                    
                return redirect('student_detail', pk=student.pk)
                
        except Exception as e:
            logger.error(f"Error updating parent assignments: {str(e)}")
            messages.error(self.request, f'Error updating parent assignments: {str(e)}')
            return self.form_invalid(form)
    
    def get_success_url(self):
        return reverse_lazy('student_detail', kwargs={'pk': self.kwargs['pk']})

