import os
from django.db.models import Q, Count, Avg, Sum, F, ExpressionWrapper, DecimalField
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
from django.http import FileResponse
from ..forms import StudentProfileForm, StudentRegistrationForm, StudentParentAssignmentForm
from ..models import Student, ClassAssignment, StudentAttendance, Fee, Grade, AcademicTerm, StudentAssignment, Timetable, FeePayment, Bill, BillPayment, BillItem, FeeInstallment, FeeDiscount
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, FormView, View
from django.urls import reverse, reverse_lazy
from .base_views import is_student, is_teacher, is_admin, is_parent

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

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

class StudentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Comprehensive student list view with role-based access control"""
    model = Student
    template_name = 'core/students/student_list.html'
    context_object_name = 'students'
    paginate_by = 20
    
    def test_func(self):
        """All authenticated users can access, but see different views"""
        return self.request.user.is_authenticated
    
    def dispatch(self, request, *args, **kwargs):
        """Handle redirection based on user role"""
        # First, authenticate
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Redirect students to their assignment library
        if is_student(request.user):
            # Check if student is trying to access assignment-related filters
            has_document = request.GET.get('has_document')
            status = request.GET.get('status')
            q = request.GET.get('q')
            
            # If student is using assignment filters, redirect to assignment library
            if has_document or status or q:
                return redirect(self.get_student_redirect_url())
            
            # Otherwise show limited profile view
            return self.student_profile_view(request)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_student_redirect_url(self):
        """Get the redirect URL for student assignment filters"""
        url = reverse('student_assignment_library')
        params = self.request.GET.copy()
        
        # Keep only assignment-related parameters
        assignment_params = {}
        if params.get('has_document'):
            assignment_params['has_document'] = params['has_document']
        if params.get('status'):
            assignment_params['status'] = params['status']
        if params.get('q'):
            assignment_params['q'] = params['q']
        
        if assignment_params:
            from urllib.parse import urlencode
            url += '?' + urlencode(assignment_params)
        
        return url
    
    def student_profile_view(self, request):
        """Render a limited view for students (their own info only)"""
        from django.shortcuts import render
        from ..models import StudentAssignment
        
        student = request.user.student
        
        # Get context data similar to StudentDashboardView
        context = {
            'student': student,
            'is_student': True,
            'is_admin': False,
            'is_teacher': False,
            'class_levels': CLASS_LEVEL_CHOICES,
            'time_now': timezone.now(),
        }
        
        # Add statistics about the student
        context['total_assignments'] = StudentAssignment.objects.filter(
            student=student
        ).count()
        
        context['pending_assignments'] = StudentAssignment.objects.filter(
            student=student,
            status__in=['PENDING', 'LATE']
        ).count()
        
        context['graded_assignments'] = StudentAssignment.objects.filter(
            student=student,
            status='GRADED'
        ).count()
        
        # Show limited student info (just themselves)
        context['students'] = [student]
        
        return render(request, 'core/students/student_limited_list.html', context)
    
    def get_queryset(self):
        """Get queryset based on user role"""
        if is_student(self.request.user):
            # Students only see themselves
            return Student.objects.filter(id=self.request.user.student.id)
        
        # Admin/Teacher: Get ALL students with any caching for debugging
        queryset = Student.objects.all().select_related('user')
        
        # Apply filters for admin/teacher
        class_level = self.request.GET.get('class_level')
        if class_level:
            queryset = queryset.filter(class_level=class_level)
        
        gender = self.request.GET.get('gender')
        if gender:
            queryset = queryset.filter(gender=gender)
        
        status = self.request.GET.get('status')
        if status:
            if status == 'active':
                queryset = queryset.filter(is_active=True)
            elif status == 'inactive':
                queryset = queryset.filter(is_active=False)
        
        # Search functionality
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(student_id__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(user__email__icontains=search_query)
            )
        
        # Date filters - FIXED: Use admission_date instead of enrollment_date
        admission_date_from = self.request.GET.get('admission_date_from')
        admission_date_to = self.request.GET.get('admission_date_to')
        if admission_date_from:
            queryset = queryset.filter(admission_date__gte=admission_date_from)
        if admission_date_to:
            queryset = queryset.filter(admission_date__lte=admission_date_to)
        
        # Ordering
        order_by = self.request.GET.get('order_by', 'student_id')
        if order_by in ['student_id', 'first_name', 'last_name', 'class_level', 'admission_date']:
            queryset = queryset.order_by(order_by)
        
        # DEBUG: Print detailed student information
        logger.debug(f"[STUDENT LIST] Total students in database: {queryset.count()}")
        students_info = list(queryset.values_list('id', 'student_id', 'first_name', 'last_name', 'class_level', 'is_active'))
        logger.debug(f"[STUDENT LIST] Students in queryset: {students_info}")
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add user role flags
        context['is_admin'] = is_admin(self.request.user)
        context['is_teacher'] = is_teacher(self.request.user)
        context['is_student'] = is_student(self.request.user)
        
        # Common context for all users
        context['class_levels'] = CLASS_LEVEL_CHOICES
        context['time_now'] = timezone.now()
        
        # If student, show limited info
        if is_student(self.request.user):
            student = self.request.user.student
            context['current_student'] = student
            context['total_students'] = 1
            
            # Add some basic statistics for student view
            from ..models import StudentAssignment
            assignments = StudentAssignment.objects.filter(student=student)
            context['assignment_stats'] = {
                'total': assignments.count(),
                'pending': assignments.filter(status__in=['PENDING', 'LATE']).count(),
                'submitted': assignments.filter(status__in=['SUBMITTED', 'LATE']).count(),
                'graded': assignments.filter(status='GRADED').count(),
            }
            
            return context
        
        # Admin/Teacher context
        queryset = self.get_queryset()
        
        # Total students count
        context['total_students'] = queryset.count()
        
        # Gender counts
        context['male_count'] = queryset.filter(gender='M').count()
        context['female_count'] = queryset.filter(gender='F').count()
        
        # Count distinct active classes
        context['class_count'] = queryset.values('class_level').distinct().count()
        
        # Class distribution for chart
        class_distribution = queryset.values('class_level').annotate(
            count=Count('id')
        ).order_by('class_level')
        context['class_distribution'] = {
            item['class_level']: item['count'] for item in class_distribution
        }
        
        # Status counts
        context['active_count'] = queryset.filter(is_active=True).count()
        context['inactive_count'] = queryset.filter(is_active=False).count()
        
        # Recent enrollments (last 30 days) - FIXED: Use admission_date instead of enrollment_date
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        context['recent_enrollments'] = queryset.filter(
            admission_date__gte=thirty_days_ago
        ).count()
        
        # Add current filters to context
        context['current_filters'] = {
            'class_level': self.request.GET.get('class_level', ''),
            'gender': self.request.GET.get('gender', ''),
            'status': self.request.GET.get('status', ''),
            'q': self.request.GET.get('q', ''),
            'admission_date_from': self.request.GET.get('admission_date_from', ''),  # Updated
            'admission_date_to': self.request.GET.get('admission_date_to', ''),  # Updated
            'order_by': self.request.GET.get('order_by', 'student_id'),
        }
        
        # DEBUG: Print context data
        logger.debug(f"[STUDENT LIST] Context total_students: {context['total_students']}")
        
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
            from django.core.exceptions import PermissionDenied
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
        from ..models import ParentGuardian
        
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
        from ..models import ParentGuardian
        
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
        from ..models import ParentGuardian
        
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
            from ..models import ParentGuardian
            parent = ParentGuardian.objects.create(
                relationship=form.cleaned_data.get('parent_relationship', 'G'),
                email=parent_email,
                phone_number=parent_phone,
                account_status='pending'
            )
            
            # Link parent to student
            parent.students.add(student)
            
            # Create user account for parent
            if parent_email and parent_email != f"parent.{student.student_id}@school.edu.gh":
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
            'paid': fees.filter(payment_status='paid').count(),
            'partial': fees.filter(payment_status='partial').count(),
            'unpaid': fees.filter(payment_status='unpaid').count(),
            'overdue': fees.filter(payment_status='overdue').count(),
        }
        
        # Summary by academic year and term
        term_summary = fees.values('academic_year', 'term').annotate(
            payable=Sum('amount_payable') or 0,
            paid=Sum('amount_paid') or 0,
            balance=Sum('balance') or 0,
            count=Count('id')
        ).order_by('-academic_year', '-term')
        
        # Get recent payments
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
        
        # ============================================
        # ASSIGNMENT DATA - ENHANCED WITH LIBRARY FEATURES
        # ============================================
        
        # Get assignments with better organization and document info
        assignments = StudentAssignment.objects.filter(
            student=student
        ).select_related(
            'assignment', 
            'assignment__subject',
            'assignment__class_assignment'
        ).prefetch_related(
            'assignment__student_assignments'
        ).order_by('assignment__due_date')
        
        # Assignment Library Statistics
        total_assignments = assignments.count()
        assignments_with_docs = assignments.filter(assignment__attachment__isnull=False).count()
        submitted_count = assignments.filter(status__in=['SUBMITTED', 'LATE', 'GRADED']).count()
        
        # Categorize assignments for enhanced dashboard
        today = timezone.now()
        
        # Overdue assignments
        context['overdue_assignments'] = [
            sa for sa in assignments 
            if sa.assignment.due_date < today and sa.status in ['PENDING', 'LATE']
        ]
        
        # Due soon (within 3 days)
        context['due_soon_assignments'] = [
            sa for sa in assignments 
            if sa.assignment.due_date <= today + timedelta(days=3) 
            and sa.status in ['PENDING', 'LATE']
            and sa.assignment.due_date >= today
        ]
        
        # Upcoming assignments
        context['upcoming_assignments'] = [
            sa for sa in assignments 
            if sa.assignment.due_date > today + timedelta(days=3)
            and sa.status in ['PENDING', 'LATE']
        ]
        
        # Completed assignments (submitted or graded)
        context['completed_assignments'] = [
            sa for sa in assignments 
            if sa.status in ['SUBMITTED', 'GRADED']
        ]
        
        # Recent assignments with documents
        context['recent_assignments_with_docs'] = assignments.filter(
            assignment__attachment__isnull=False
        ).order_by('-assignment__created_at')[:5]
        
        # Progress statistics
        completed_count = len(context['completed_assignments'])
        context['completion_rate'] = round((completed_count / total_assignments * 100), 1) if total_assignments > 0 else 0
        
        # Assignment counts for dashboard cards
        pending_assignments = len([a for a in assignments if a.status in ['PENDING', 'LATE']])
        submitted_assignments = len([a for a in assignments if a.status in ['SUBMITTED', 'LATE']])
        graded_assignments = len([a for a in assignments if a.status == 'GRADED'])
        due_soon_assignments = len(context['due_soon_assignments'])
        
        # Assignment Library Stats
        context['total_assignments'] = total_assignments
        context['assignments_with_docs'] = assignments_with_docs
        context['submission_rate'] = round((submitted_count / total_assignments * 100), 1) if total_assignments > 0 else 0
        
        # Assignment stats dictionary for cards
        context['assignment_stats'] = {
            'total': total_assignments,
            'pending': pending_assignments,
            'submitted': submitted_assignments,
            'graded': graded_assignments,
            'with_docs': assignments_with_docs,
            'submission_rate': context['submission_rate'],
            'due_soon': due_soon_assignments,
            'overdue': len(context['overdue_assignments']),
        }
        
        # ============================================
        # FEE DATA - COMPREHENSIVE (FIXED None HANDLING)
        # ============================================
        
        fees = Fee.objects.filter(student=student).select_related('category')
        
        # Calculate fee totals with proper handling of None values
        fee_aggregates = fees.aggregate(
            total_payable=Sum('amount_payable'),
            total_paid=Sum('amount_paid'),
            total_balance=Sum('balance')
        )
        
        # Use or 0 to handle None values
        total_payable = fee_aggregates['total_payable'] or 0
        total_paid = fee_aggregates['total_paid'] or 0
        total_balance = total_payable - total_paid  # Calculate balance directly
        
        # More accurate fee status calculation with None handling
        if total_balance is not None and total_balance <= 0 and fees.exists():
            fee_status = 'paid'
            fee_status_class = 'success'
            fee_status_icon = 'bi-check-circle'
            fee_message = 'All fees are paid'
        elif total_paid is not None and total_paid > 0:
            fee_status = 'partial'
            fee_status_class = 'warning'
            fee_status_icon = 'bi-exclamation-circle'
            fee_message = f'GH₵{total_balance:,.2f} balance remaining'
        else:
            fee_status = 'unpaid'
            fee_status_class = 'danger'
            fee_status_icon = 'bi-x-circle'
            fee_message = 'No payments made yet'
        
        # Check for overdue fees
        overdue_fees = fees.filter(
            due_date__lt=timezone.now().date(),
            payment_status__in=['unpaid', 'partial', 'overdue']
        ).exists()
        
        # Get fee status breakdown
        fee_status_counts = {
            'paid': fees.filter(payment_status='paid').count(),
            'partial': fees.filter(payment_status='partial').count(),
            'unpaid': fees.filter(payment_status='unpaid').count(),
            'overdue': fees.filter(payment_status='overdue').count(),
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
                payment_status__in=['unpaid', 'partial']
            ).count(),
            'paid_count': fees.filter(payment_status='paid').count(),
            'partial_count': fees.filter(payment_status='partial').count(),
            'unpaid_count': fees.filter(payment_status='unpaid').count(),
            'status': fee_status,
            'status_class': fee_status_class,
            'status_icon': fee_status_icon,
            'message': fee_message,
            'has_fees': fees.exists(),
        }
        
        # ============================================
        # GRADE DATA
        # ============================================
        
        # Calculate average grade for current term
        current_grades = Grade.objects.filter(
            student=student,
            academic_year=academic_year,
            term=current_term.term if current_term else 1
        )
        average_grade_result = current_grades.aggregate(Avg('total_score'))
        average_grade = average_grade_result['total_score__avg'] or 0
        
        # Get recent grades
        recent_grades = Grade.objects.filter(
            student=student
        ).select_related('subject').order_by('-last_updated')[:5]
        
        # ============================================
        # ATTENDANCE DATA
        # ============================================
        
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
        
        # Calculate attendance percentage with None handling
        total_attendance = attendance_summary['total'] or 0
        present_count = attendance_summary['present'] or 0
        attendance_percentage = round((present_count / total_attendance * 100), 1) if total_attendance > 0 else 0
        
        # ============================================
        # TIMETABLE DATA
        # ============================================
        
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
        
        # ============================================
        # KEYBOARD SHORTCUTS FOR ENHANCED NAVIGATION
        # ============================================
        
        context['keyboard_shortcuts'] = {
            'assignment_library': 'Alt + L',
            'download_document': 'Alt + D',
            'navigation_dashboard': 'Alt + 1',
            'navigation_assignments': 'Alt + 2',
            'navigation_grades': 'Alt + 3',
            'navigation_fees': 'Alt + 4',
            'navigation_attendance': 'Alt + 5',
        }
        
        # ============================================
        # QUICK ACTIONS FOR DASHBOARD
        # ============================================
        
        context['quick_actions'] = [
            {
                'title': 'Assignment Library',
                'icon': 'bi-journal-text',
                'url': reverse('student_assignment_library'),
                'color': 'purple',
                'description': 'Access all assignments with documents',
                'shortcut': 'Alt + L'
            },
            {
                'title': 'Submit Assignment',
                'icon': 'bi-upload',
                'url': reverse('student_assignment_library'),
                'color': 'primary',
                'description': 'Submit pending assignments',
                'shortcut': 'Alt + S'
            },
            {
                'title': 'View Grades',
                'icon': 'bi-award',
                'url': reverse('student_grades'),
                'color': 'success',
                'description': 'Check your grades and performance',
                'shortcut': 'Alt + G'
            },
            {
                'title': 'Pay Fees',
                'icon': 'bi-cash-coin',
                'url': reverse('student_fees'),
                'color': 'warning',
                'description': 'View and pay school fees',
                'shortcut': 'Alt + F'
            },
            {
                'title': 'View Timetable',
                'icon': 'bi-calendar-week',
                'url': reverse('student_timetable'),
                'color': 'info',
                'description': 'See your class schedule',
                'shortcut': 'Alt + T'
            },
        ]
        
        # ============================================
        # RECENT ACTIVITY
        # ============================================
        
        # Get recent activity from multiple sources
        recent_activities = []
        
        # Recent graded assignments
        for assignment in assignments.filter(status='GRADED').order_by('-graded_date')[:3]:
            recent_activities.append({
                'type': 'assignment_graded',
                'title': f'"{assignment.assignment.title}" graded',
                'description': f'Score: {assignment.score}/{assignment.assignment.max_score}',
                'icon': 'bi-check-circle-fill',
                'color': 'success',
                'time': assignment.graded_date if assignment.graded_date else assignment.assignment.due_date,
                'url': reverse('student_assignment_detail', kwargs={'pk': assignment.pk})
            })
        
        # Recent payments
        for payment in recent_payments:
            recent_activities.append({
                'type': 'payment_made',
                'title': f'Fee payment: GH₵{payment.amount:,.2f}',
                'description': payment.fee.category.name,
                'icon': 'bi-cash-stack',
                'color': 'success',
                'time': payment.payment_date,
                'url': reverse('student_fees')
            })
        
        # Sort activities by time
        recent_activities.sort(key=lambda x: x['time'], reverse=True)
        context['recent_activities'] = recent_activities[:5]  # Limit to 5 most recent
        
        # ============================================
        # UPDATE CONTEXT WITH ALL DATA
        # ============================================
        
        context.update({
            'student': student,
            
            # Enhanced Assignment data
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
            
            # Performance indicators
            'performance_score': round((context['completion_rate'] + attendance_percentage + (average_grade if average_grade else 0)) / 3, 1),
            'has_missing_assignments': pending_assignments > 0,
            'has_overdue_assignments': len(context['overdue_assignments']) > 0,
            'needs_attention': pending_assignments > 0 or len(context['overdue_assignments']) > 0 or total_balance > 0,
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
        all_parents = Student.parents.field.model.objects.all().select_related('user')
        
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


#student assignment documents view

class StudentAssignmentDocumentView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View assignment documents provided by teacher"""
    model = StudentAssignment
    template_name = 'core/students/assignment_documents.html'
    context_object_name = 'assignments'
    paginate_by = 10
    
    def test_func(self):
        return is_student(self.request.user)
    
    def get_queryset(self):
        student = self.request.user.student
    
        # FIXED: Filter out empty strings
        from django.db.models import Q
        queryset = StudentAssignment.objects.filter(
            student=student
        ).filter(
            Q(assignment__attachment__isnull=False) & 
            ~Q(assignment__attachment='')  # Exclude empty strings
        ).select_related('assignment')
    
        # Apply other filters...
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student
        
        # Get statistics
        assignments = self.get_queryset()
        context['assignments_with_docs'] = assignments.filter(
            assignment__attachment__isnull=False
        ).count()
        
        # Calculate submission rate
        total_assignments = assignments.count()
        submitted_count = assignments.filter(status__in=['SUBMITTED', 'LATE', 'GRADED']).count()
        context['submission_rate'] = round((submitted_count / total_assignments * 100), 1) if total_assignments > 0 else 0
        
        # Get subjects for filter dropdown
        from ..models import Subject
        context['subjects'] = Subject.objects.filter(
            classassignment__class_level=student.class_level
        ).distinct()
        
        return context


class StudentAssignmentLibraryView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Complete assignment library for students with document access"""
    model = StudentAssignment
    template_name = 'core/students/assignment_library.html'
    context_object_name = 'student_assignments'
    paginate_by = 10
    
    def test_func(self):
        return is_student(self.request.user)
    
    def get_queryset(self):
        student = self.request.user.student
        
        # Get all student assignments with related data
        return StudentAssignment.objects.filter(
            student=student
        ).select_related(
            'assignment',
            'assignment__subject',
            'assignment__class_assignment',
            'assignment__class_assignment__teacher',
            'assignment__class_assignment__teacher__user'
        ).prefetch_related(
            'assignment__student_assignments'
        ).order_by('-assignment__due_date', '-submitted_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student
        
        # Get all student assignments
        all_assignments = self.get_queryset()
        
        # Categorize assignments
        context['upcoming_assignments'] = [
            sa for sa in all_assignments 
            if sa.assignment.due_date >= timezone.now() and sa.status in ['PENDING', 'LATE']
        ]
        
        context['submitted_assignments'] = [
            sa for sa in all_assignments 
            if sa.status in ['SUBMITTED', 'LATE'] and sa.submitted_date is not None
        ]
        
        context['graded_assignments'] = [
            sa for sa in all_assignments 
            if sa.status == 'GRADED'
        ]
        
        context['overdue_assignments'] = [
            sa for sa in all_assignments 
            if sa.assignment.due_date < timezone.now() and sa.status in ['PENDING', 'LATE']
        ]
        
        # Statistics
        context['total_assignments'] = all_assignments.count()
        context['graded_count'] = len(context['graded_assignments'])
        context['submitted_count'] = len(context['submitted_assignments'])
        context['pending_count'] = len(context['upcoming_assignments']) + len(context['overdue_assignments'])
        
        # Calculate submission rate
        if context['total_assignments'] > 0:
            context['submission_rate'] = round((context['submitted_count'] + context['graded_count']) / context['total_assignments'] * 100, 1)
        else:
            context['submission_rate'] = 0
            
        # Check for assignments with teacher documents
        context['assignments_with_docs'] = all_assignments.filter(
            assignment__attachment__isnull=False
        ).count()
        
        # Get current term for filtering
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        context['current_term'] = current_term
        
        return context



class StudentAssignmentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Detailed view of a specific assignment with all documents"""
    model = StudentAssignment
    template_name = 'core/students/assignment_detail.html'
    context_object_name = 'student_assignment'
    
    def test_func(self):
        # Only the student who owns this assignment can view it
        return is_student(self.request.user) and self.get_object().student == self.request.user.student
    
    def get_object(self):
        # Get the student assignment with all related data
        return get_object_or_404(
            StudentAssignment.objects.select_related(
                'assignment',
                'assignment__subject',
                'assignment__class_assignment',
                'assignment__class_assignment__teacher',
                'assignment__class_assignment__teacher__user',
                'student'
            ),
            pk=self.kwargs['pk'],
            student=self.request.user.student
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student_assignment = self.object
        
        # Get related assignments in the same subject
        context['related_assignments'] = StudentAssignment.objects.filter(
            student=self.request.user.student,
            assignment__subject=student_assignment.assignment.subject
        ).exclude(pk=student_assignment.pk).select_related(
            'assignment'
        ).order_by('-assignment__due_date')[:5]
        
        # Calculate days until due
        due_date = student_assignment.assignment.due_date
        if due_date:
            days_left = (due_date - timezone.now()).days
            context['days_left'] = days_left
            context['is_overdue'] = days_left < 0
            context['due_soon'] = 0 <= days_left <= 3
        
        # Check if submission is allowed
        context['can_submit'] = student_assignment.status in ['PENDING', 'LATE'] and student_assignment.assignment.due_date >= timezone.now()
        
        # Check if feedback is available
        context['has_feedback'] = student_assignment.status == 'GRADED' and (student_assignment.feedback or student_assignment.score is not None)
        
        return context


class DownloadAssignmentDocumentView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Download teacher's assignment document with proper file format"""
    
    def test_func(self):
        from .base_views import is_student
        return is_student(self.request.user)
    
    def get(self, request, pk):
        from ..models import Assignment
        from django.core.exceptions import PermissionDenied
        import mimetypes
        
        assignment = get_object_or_404(
            Assignment.objects.select_related('class_assignment'),
            pk=pk
        )
        
        # Verify student is in the same class
        student = request.user.student
        if student.class_level != assignment.class_assignment.class_level:
            raise PermissionDenied("You don't have access to this assignment document.")
        
        if assignment.attachment and assignment.attachment.name:
            try:
                # Get file information
                file_name = assignment.attachment.name
                file_extension = os.path.splitext(file_name)[1].lower()
                
                # Map extensions to proper MIME types
                mime_type_mapping = {
                    '.doc': 'application/msword',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.pdf': 'application/pdf',
                    '.txt': 'text/plain',
                    '.rtf': 'application/rtf',
                    '.odt': 'application/vnd.oasis.opendocument.text',
                    '.ppt': 'application/vnd.ms-powerpoint',
                    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    '.xls': 'application/vnd.ms-excel',
                    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                }
                
                # Get MIME type from mapping or use Django's guess
                content_type = mime_type_mapping.get(file_extension)
                if not content_type:
                    content_type, _ = mimetypes.guess_type(file_name)
                    if not content_type:
                        content_type = 'application/octet-stream'
                
                # Create response with proper headers
                response = FileResponse(
                    assignment.attachment.open('rb'),
                    content_type=content_type,
                    as_attachment=True,  # This forces download instead of opening in browser
                    filename=os.path.basename(file_name)
                )
                
                # Critical: Prevent browser from sniffing MIME type
                response['X-Content-Type-Options'] = 'nosniff'
                
                # Add cache control
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                
                return response
                
            except Exception as e:
                logger.error(f"Error downloading assignment document: {str(e)}")
                messages.error(request, f"Error downloading file: {str(e)}")
                return redirect('student_assignment_library')
        else:
            messages.error(request, "No document available for this assignment.")
            return redirect('student_assignment_library')


class StudentSubmittedAssignmentsView(StudentAssignmentLibraryView):
    """Filter view for submitted assignments only"""
    def get_queryset(self):
        return super().get_queryset().filter(status__in=['SUBMITTED', 'LATE'])


class StudentGradedAssignmentsView(StudentAssignmentLibraryView):
    """Filter view for graded assignments only"""
    def get_queryset(self):
        return super().get_queryset().filter(status='GRADED')