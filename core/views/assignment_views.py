from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404, render, redirect  # ADDED redirect here
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
import datetime
import json
import logging

from ..models import Assignment, StudentAssignment, ClassAssignment, Subject, Student, CLASS_LEVEL_CHOICES, AssignmentAnalytics, Teacher
from .base_views import is_admin, is_teacher, is_student
from ..forms import AssignmentForm, StudentAssignmentForm
from core.forms import StudentAssignmentSubmissionForm

logger = logging.getLogger(__name__)

def get_current_academic_year():
    """Helper function to get current academic year"""
    current_year = timezone.now().year
    return f"{current_year}/{current_year + 1}"


class TeacherOwnershipRequiredMixin:
    """Mixin to verify that the current user (teacher) owns the object."""
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        
        # Allow admins to edit any assignment
        if is_admin(request.user):
            return super().dispatch(request, *args, **kwargs)
        
        # Check if user has a teacher profile
        if not is_teacher(request.user):
            raise PermissionDenied("You need to have a teacher profile to access this resource.")
        
        # Check ownership for teachers
        if hasattr(obj, 'teacher') and obj.teacher != request.user.teacher:
            raise PermissionDenied("You do not have permission to edit this assignment.")
        elif hasattr(obj, 'class_assignment') and obj.class_assignment.teacher != request.user.teacher:
            raise PermissionDenied("You do not have permission to edit this assignment.")
        
        return super().dispatch(request, *args, **kwargs)


class AssignmentListView(LoginRequiredMixin, ListView):
    model = Assignment
    template_name = 'core/academics/assignments/assignment_list.html'
    context_object_name = 'assignments'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'subject', 'class_assignment', 'class_assignment__teacher'
        ).prefetch_related('student_assignments')
        
        # Get all filter parameters
        subject_id = self.request.GET.get('subject')
        class_level = self.request.GET.get('class_level')
        assignment_type = self.request.GET.get('assignment_type')
        status = self.request.GET.get('status')
        search_query = self.request.GET.get('q')
        sort = self.request.GET.get('sort', '-due_date')

        # Build filters dynamically
        filters = Q()
        if subject_id:
            filters &= Q(subject_id=subject_id)
        if class_level:
            filters &= Q(class_assignment__class_level=class_level)
        if assignment_type:
            filters &= Q(assignment_type=assignment_type)
            
        # Status filter (for students, it's their status; for teachers, it's a general filter)
        if status and is_student(self.request.user):
            filters &= Q(student_assignments__student=self.request.user.student, 
                        student_assignments__status=status)
        elif status and (is_teacher(self.request.user) or is_admin(self.request.user)):
            # For teachers/admins, filter assignments that have at least one student with this status
            filters &= Q(student_assignments__status=status)
            
        # Search
        if search_query:
            filters &= Q(title__icontains=search_query) | Q(description__icontains=search_query)

        queryset = queryset.filter(filters)
        
        # User-specific filtering - FIXED FOR STUDENTS
        if is_teacher(self.request.user):
            queryset = queryset.filter(class_assignment__teacher=self.request.user.teacher)
        elif is_student(self.request.user):
            # Get the student's class level and filter assignments for that level
            student_class_level = self.request.user.student.class_level
            queryset = queryset.filter(class_assignment__class_level=student_class_level)

        # Apply sorting
        if sort == 'title':
            queryset = queryset.order_by('title')
        elif sort == 'created':
            queryset = queryset.order_by('-created_at')
        elif sort == 'due_date':
            queryset = queryset.order_by('due_date')
        else:  # Default sort by due_date descending
            queryset = queryset.order_by('-due_date')
        
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['time_now'] = timezone.now()
        
        # Make sure CLASS_LEVEL_CHOICES is properly imported and passed
        from ..models import CLASS_LEVEL_CHOICES
        context['class_levels'] = CLASS_LEVEL_CHOICES
        
        context['assignment_types'] = Assignment.ASSIGNMENT_TYPES
        context['status_choices'] = Assignment.STATUS_CHOICES
        
        context['current_query'] = self.request.GET.get('q', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_sort'] = self.request.GET.get('sort', '-due_date')
        context['current_class_level'] = self.request.GET.get('class_level', '')
        context['current_subject'] = self.request.GET.get('subject', '')
        context['current_assignment_type'] = self.request.GET.get('assignment_type', '')
        
        # Add the missing imports at the top of your views file
        from .base_views import is_admin, is_teacher, is_student
        
        if is_teacher(self.request.user):
            context['subjects'] = Subject.objects.filter(teachers=self.request.user.teacher)
            context['is_teacher'] = True
        elif is_student(self.request.user):
            context['subjects'] = Subject.objects.filter(
                classassignment__class_level=self.request.user.student.class_level
            ).distinct()
            context['is_student'] = True
        else:  # Admin
            context['subjects'] = Subject.objects.all()
            context['is_admin'] = True
        
        # Add stats for the template
        queryset = self.get_queryset()
        context['assignments_count'] = queryset.count()
        
        # Get current date for comparison
        current_date = timezone.now().date()
        
        # Get student assignments for status counts
        if self.request.user.is_authenticated:
            if is_student(self.request.user):
                student_assignments = StudentAssignment.objects.filter(
                    student=self.request.user.student,
                    assignment__in=queryset
                )
                context['completed_count'] = student_assignments.filter(status='GRADED').count()
                context['pending_count'] = student_assignments.filter(status='PENDING').count()
                
                # Calculate overdue count
                overdue_count = 0
                for assignment in queryset:
                    if (assignment.due_date.date() < current_date and 
                        not student_assignments.filter(assignment=assignment, status='GRADED').exists()):
                        overdue_count += 1
                context['overdue_count'] = overdue_count
                
                # Add completion percentages for student view
                for assignment in context['assignments']:
                    try:
                        student_assignment = student_assignments.get(assignment=assignment)
                        assignment.completion_percentage = 100 if student_assignment.status == 'GRADED' else 50
                    except StudentAssignment.DoesNotExist:
                        assignment.completion_percentage = 0
                        
            else:
                # For teachers/admins, show general stats
                context['completed_count'] = StudentAssignment.objects.filter(
                    assignment__in=queryset, status='GRADED'
                ).count()
                context['pending_count'] = StudentAssignment.objects.filter(
                    assignment__in=queryset, status='PENDING'
                ).count()
                
                # Calculate overdue count
                overdue_count = 0
                for assignment in queryset:
                    if (assignment.due_date.date() < current_date and 
                        not StudentAssignment.objects.filter(assignment=assignment, status='GRADED').exists()):
                        overdue_count += 1
                context['overdue_count'] = overdue_count
        else:
            context['completed_count'] = 0
            context['pending_count'] = 0
            context['overdue_count'] = 0
        
        return context


class AssignmentCreateSelectionView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Step 1: Teacher selects class and subject before creating assignment"""
    template_name = 'core/academics/assignments/assignment_create_selection.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current academic year
        academic_year = get_current_academic_year()
        
        # Get teacher's assigned classes and subjects
        if is_teacher(self.request.user):
            teacher = self.request.user.teacher
            class_assignments = ClassAssignment.objects.filter(
                teacher=teacher,
                academic_year=academic_year,
                is_active=True
            ).select_related('subject')
            
            # DEBUG: Print all class assignments
            print(f"DEBUG: Teacher {teacher.get_full_name()} has {class_assignments.count()} class assignments:")
            for ca in class_assignments:
                print(f"  - ID: {ca.id}, Class level: '{ca.class_level}'")
            
            # Group by class level with better handling
            assignments_by_class = {}
            for ca in class_assignments:
                # Get display name, fallback to the code itself
                class_display = dict(CLASS_LEVEL_CHOICES).get(ca.class_level)
                if not class_display:
                    # If not found in choices, use a formatted version
                    if ca.class_level == 'FORM_1':
                        class_display = 'Form 1'
                    else:
                        class_display = ca.class_level.replace('_', ' ').title()
                
                if class_display not in assignments_by_class:
                    assignments_by_class[class_display] = []
                assignments_by_class[class_display].append({
                    'id': ca.id,
                    'subject': ca.subject,
                    'class_level_code': ca.class_level,
                    'can_create': True
                })
            
            print(f"DEBUG: Grouped assignments: {assignments_by_class}")
            
            # Also show available subjects for teacher's expertise even if not assigned
            teacher_subjects = teacher.subjects.filter(is_active=True)
            teacher_class_levels = teacher.class_levels.split(',') if teacher.class_levels else []
            
            # Clean up class levels
            teacher_class_levels = [level.strip() for level in teacher_class_levels]
            
            available_combinations = []
            for subject in teacher_subjects:
                for class_level in teacher_class_levels:
                    # Check if already assigned
                    already_assigned = False
                    for ca_list in assignments_by_class.values():
                        for ca in ca_list:
                            if ca['subject'].id == subject.id and ca['class_level_code'] == class_level:
                                already_assigned = True
                                break
                        if already_assigned:
                            break
                    
                    if not already_assigned:
                        class_display = dict(CLASS_LEVEL_CHOICES).get(class_level, class_level)
                        available_combinations.append({
                            'subject': subject,
                            'class_level': class_display,
                            'class_level_code': class_level,
                            'can_create': False,
                            'message': 'Not officially assigned to this class'
                        })
            
            context['assignments_by_class'] = assignments_by_class
            context['available_combinations'] = available_combinations
            context['has_assignments'] = bool(assignments_by_class)
            
        elif is_admin(self.request.user):
            # Admin sees all possible combinations
            all_subjects = Subject.objects.filter(is_active=True)
            all_class_assignments = {}
            
            for class_code, class_name in CLASS_LEVEL_CHOICES:
                assignments = ClassAssignment.objects.filter(
                    class_level=class_code,
                    academic_year=academic_year,
                    is_active=True
                ).select_related('subject', 'teacher')
                
                if assignments.exists():
                    all_class_assignments[class_name] = []
                    for ca in assignments:
                        all_class_assignments[class_name].append({
                            'id': ca.id,
                            'subject': ca.subject,
                            'teacher': ca.teacher,
                            'class_level_code': ca.class_level,
                            'can_create': True
                        })
            
            # Also include any assignments with class levels not in CHOICES
            other_assignments = ClassAssignment.objects.filter(
                academic_year=academic_year,
                is_active=True
            ).exclude(class_level__in=[code for code, _ in CLASS_LEVEL_CHOICES])
            
            for ca in other_assignments:
                class_display = ca.class_level.replace('_', ' ').title()
                if class_display not in all_class_assignments:
                    all_class_assignments[class_display] = []
                all_class_assignments[class_display].append({
                    'id': ca.id,
                    'subject': ca.subject,
                    'teacher': ca.teacher,
                    'class_level_code': ca.class_level,
                    'can_create': True
                })
            
            context['assignments_by_class'] = all_class_assignments
            context['has_assignments'] = bool(all_class_assignments)
        
        context['academic_year'] = academic_year
        context['is_admin'] = is_admin(self.request.user)
        context['is_teacher'] = is_teacher(self.request.user)
        return context



class AssignmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Step 2: Create assignment with pre-selected class and subject"""
    model = Assignment
    form_class = AssignmentForm
    template_name = 'core/academics/assignments/assignment_form.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def setup(self, request, *args, **kwargs):
        """Setup method - called before dispatch()"""
        super().setup(request, *args, **kwargs)
        
        # Store parameters as instance attributes
        self.class_assignment_id = request.GET.get('class_assignment')
        self.class_level = request.GET.get('class_level')
        self.subject_id = request.GET.get('subject')
        
        # Log for debugging
        logger.info(f"AssignmentCreateView setup - class_assignment_id: {self.class_assignment_id}, "
                   f"class_level: {self.class_level}, subject_id: {self.subject_id}")
    
    def dispatch(self, request, *args, **kwargs):
        """Main entry point - validate parameters before any HTTP method"""
        # Check user permissions first
        if not self.test_func():
            logger.error(f"User {request.user} doesn't have permission to create assignments")
            return HttpResponseForbidden("You don't have permission to create assignments.")
        
        # Validate parameters
        if not self.class_assignment_id and (not self.class_level or not self.subject_id):
            logger.error("Missing required parameters")
            logger.error(f"class_assignment_id: {self.class_assignment_id}")
            logger.error(f"class_level: {self.class_level}")
            logger.error(f"subject_id: {self.subject_id}")
            
            messages.error(request, "Missing required parameters. Please select a class and subject first.")
            return redirect('assignment_create_selection')
        
        # If class_assignment_id is provided, validate it exists
        if self.class_assignment_id:
            try:
                class_assignment = ClassAssignment.objects.get(id=self.class_assignment_id)
                
                # Check if teacher owns this class assignment
                if is_teacher(request.user) and class_assignment.teacher != request.user.teacher:
                    logger.error(f"Teacher {request.user.teacher} doesn't own class assignment {class_assignment.id}")
                    messages.error(request, "You don't have permission to create assignments for this class.")
                    return redirect('assignment_create_selection')
                    
            except ClassAssignment.DoesNotExist:
                logger.error(f"ClassAssignment with ID {self.class_assignment_id} does not exist")
                messages.error(request, "Selected class assignment not found.")
                return redirect('assignment_create_selection')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Pass parameters to the form"""
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'request': self.request,
            'class_assignment_id': self.class_assignment_id,
            'class_level': self.class_level,
            'subject_id': self.subject_id
        })
        return kwargs
    
    def get_context_data(self, **kwargs):
        """Add context information for the template"""
        context = super().get_context_data(**kwargs)
        
        # Add context information
        if self.class_assignment_id:
            try:
                class_assignment = ClassAssignment.objects.get(id=self.class_assignment_id)
                context['selected_class_assignment'] = class_assignment
                context['selected_class'] = class_assignment.get_class_level_display()
                context['selected_subject'] = class_assignment.subject
                context['selected_teacher'] = class_assignment.teacher
                context['academic_year'] = class_assignment.academic_year
            except ClassAssignment.DoesNotExist:
                messages.error(self.request, "Selected class assignment not found.")
                context['selected_class'] = "Unknown"
                context['selected_subject'] = None
                context['selected_teacher'] = None
        elif self.class_level and self.subject_id:
            try:
                subject = Subject.objects.get(id=self.subject_id)
                context['selected_class'] = dict(CLASS_LEVEL_CHOICES).get(self.class_level, self.class_level)
                context['selected_subject'] = subject
                context['academic_year'] = get_current_academic_year()
                
                # Try to find available teachers
                available_teachers = Teacher.objects.filter(
                    subjects=subject,
                    is_active=True
                )
                context['available_teachers'] = available_teachers
                
                # For admin, show all teachers; for teacher, show only themselves if qualified
                if is_teacher(self.request.user) and self.request.user.teacher in available_teachers:
                    context['selected_teacher'] = self.request.user.teacher
                else:
                    context['selected_teacher'] = None
                    
            except Subject.DoesNotExist:
                messages.error(self.request, "Selected subject not found.")
                context['selected_class'] = dict(CLASS_LEVEL_CHOICES).get(self.class_level, self.class_level)
                context['selected_subject'] = None
                context['selected_teacher'] = None
        
        # Add user role flags
        context['is_admin'] = is_admin(self.request.user)
        context['is_teacher'] = is_teacher(self.request.user)
        
        return context
    
    def form_valid(self, form):
        """Handle form validation"""
        print(f"DEBUG VIEW: form_valid called")
        
        # Save the assignment first
        response = super().form_valid(form)
        
        # Send notifications to students after assignment is created
        self.send_assignment_notifications()
        
        messages.success(self.request, 'Assignment created successfully!')
        print(f"DEBUG VIEW: form_valid completed, object pk = {self.object.pk}")
        return response
    
    def send_assignment_notifications(self):
        """Send notifications to all students in the class about the new assignment"""
        assignment = self.object
        
        try:
            # Get all students in the class level
            from core.models import Student
            students = Student.objects.filter(class_level=assignment.class_assignment.class_level)
            
            for student in students:
                # Create notification for each student
                from core.views.notifications_views import create_notification
                create_notification(
                    recipient=student.user,
                    title="New Assignment Created",
                    message=f"New assignment '{assignment.title}' has been created for {assignment.subject.name}. Due date: {assignment.due_date.strftime('%b %d, %Y')}",
                    notification_type="ASSIGNMENT",
                    link=reverse('assignment_detail', kwargs={'pk': assignment.pk})
                )
            
            print(f"DEBUG: Sent assignment notifications to {students.count()} students")
            
        except Exception as e:
            print(f"ERROR: Failed to send assignment notifications: {str(e)}")
            # Don't raise the exception to avoid breaking the assignment creation
    
    def form_invalid(self, form):
        """Handle form invalidation"""
        print(f"DEBUG VIEW: form_invalid called")
        print(f"DEBUG VIEW: Form errors: {form.errors}")
        print(f"DEBUG VIEW: Form non-field errors: {form.non_field_errors()}")
        return super().form_invalid(form)
    
    def get_success_url(self):
        """Redirect to assignment detail after creation"""
        return reverse_lazy('assignment_detail', kwargs={'pk': self.object.pk})

class QuickClassAssignmentView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Quick view to assign teacher to subject/class before creating assignment"""
    template_name = 'core/academics/assignments/quick_class_assignment.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get(self, request, *args, **kwargs):
        class_level = request.GET.get('class_level')
        subject_id = request.GET.get('subject')
        
        if not class_level or not subject_id:
            messages.error(request, "Please select both class level and subject")
            return redirect('assignment_create_selection')
        
        try:
            subject = Subject.objects.get(id=subject_id, is_active=True)
        except Subject.DoesNotExist:
            messages.error(request, "Selected subject not found")
            return redirect('assignment_create_selection')
        
        # Get current academic year
        academic_year = get_current_academic_year()
        
        # Check if assignment already exists
        existing_assignment = ClassAssignment.objects.filter(
            class_level=class_level,
            subject=subject,
            academic_year=academic_year
        ).first()
        
        if existing_assignment:
            # Redirect to create assignment with existing class assignment
            return redirect(f"{reverse('assignment_create')}?class_assignment={existing_assignment.id}")
        
        # Get available teachers
        available_teachers = Teacher.objects.filter(
            subjects=subject,
            is_active=True
        )
        
        context = {
            'class_level': class_level,
            'class_level_display': dict(CLASS_LEVEL_CHOICES).get(class_level, class_level),
            'subject': subject,
            'available_teachers': available_teachers,
            'academic_year': academic_year,
            'is_admin': is_admin(request.user),
            'is_teacher': is_teacher(request.user),
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        class_level = request.POST.get('class_level')
        subject_id = request.POST.get('subject_id')
        teacher_id = request.POST.get('teacher_id')
        
        if not all([class_level, subject_id, teacher_id]):
            messages.error(request, "Please provide all required information")
            return redirect('assignment_create_selection')
        
        try:
            subject = Subject.objects.get(id=subject_id, is_active=True)
            teacher = Teacher.objects.get(id=teacher_id, is_active=True)
            
            # Check if teacher is qualified to teach this subject
            if subject not in teacher.subjects.all():
                messages.error(request, f"{teacher.get_full_name()} is not qualified to teach {subject.name}")
                return redirect('assignment_create_selection')
            
            # Check if assignment already exists
            academic_year = get_current_academic_year()
            existing_assignment = ClassAssignment.objects.filter(
                class_level=class_level,
                subject=subject,
                academic_year=academic_year
            ).first()
            
            if existing_assignment:
                messages.info(request, f"Assignment already exists. Redirecting to create assignment.")
                return redirect(f"{reverse('assignment_create')}?class_assignment={existing_assignment.id}")
            
            # Create class assignment
            class_assignment = ClassAssignment.objects.create(
                class_level=class_level,
                subject=subject,
                teacher=teacher,
                academic_year=academic_year,
                is_active=True
            )
            
            messages.success(request, f"Successfully assigned {teacher.get_full_name()} to teach {subject.name} in {dict(CLASS_LEVEL_CHOICES).get(class_level, class_level)}")
            
            # Redirect to create assignment
            return redirect(f"{reverse('assignment_create')}?class_assignment={class_assignment.id}")
            
        except (Subject.DoesNotExist, Teacher.DoesNotExist) as e:
            messages.error(request, f"Error creating assignment: {str(e)}")
            return redirect('assignment_create_selection')


class AssignmentDetailView(LoginRequiredMixin, DetailView):
    model = Assignment
    template_name = 'core/academics/assignments/assignment_detail.html'
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'subject', 'class_assignment', 'class_assignment__teacher'
        ).prefetch_related(
            'student_assignments__student__user'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.object
        
        # Add user role flags
        context['is_teacher'] = is_teacher(self.request.user)
        context['is_student'] = is_student(self.request.user)
        context['is_admin'] = is_admin(self.request.user)
        
        # Handle student assignments with enhanced functionality
        if is_student(self.request.user):
            student_assignment, created = StudentAssignment.objects.get_or_create(
                assignment=assignment,
                student=self.request.user.student,
                defaults={'status': 'PENDING'}
            )
            
            if created:
                logger.info(
                    f"Created new StudentAssignment for student {self.request.user.student.student_id} "
                    f"({self.request.user.student.get_full_name()}) and assignment '{assignment.title}'"
                )
            
            context['student_assignment'] = student_assignment
            context['student_assignment_id'] = student_assignment.id
            context['can_download_assignment'] = student_assignment.can_student_download_assignment()
            context['assignment_document_url'] = student_assignment.get_assignment_document_url()
            context['can_submit'] = student_assignment.can_student_submit_work()[0]
            
            # Students don't see other students' submissions
            context['student_assignments'] = StudentAssignment.objects.none()
            context['submitted_count'] = 0
            context['submission_rate'] = 0
        else:
            # Teachers/admins see all submissions with enhanced info
            student_assignments = assignment.student_assignments.all().select_related('student')
            context['student_assignments'] = student_assignments
            
            # Enhanced submission statistics
            total_students = student_assignments.count()
            submitted_count = student_assignments.exclude(status='PENDING').count()
            graded_count = student_assignments.filter(status='GRADED').count()
            late_count = student_assignments.filter(status='LATE').count()
            
            context.update({
                'submitted_count': submitted_count,
                'graded_count': graded_count,
                'late_count': late_count,
                'submission_rate': (submitted_count / total_students * 100) if total_students > 0 else 0,
                'grading_rate': (graded_count / total_students * 100) if total_students > 0 else 0,
            })
        
        # Get analytics data
        try:
            analytics = assignment.get_analytics()
            context['analytics'] = analytics
        except Exception as e:
            logger.error(f"Error getting analytics for assignment {assignment.id}: {str(e)}")
            context['analytics'] = None
        
        # Permission check for editing and downloads
        if is_teacher(self.request.user):
            context['can_edit'] = (assignment.class_assignment.teacher == self.request.user.teacher)
        else:
            context['can_edit'] = is_admin(self.request.user)
            
        return context


class AssignmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, TeacherOwnershipRequiredMixin, UpdateView):
    model = Assignment
    form_class = AssignmentForm
    template_name = 'core/academics/assignments/assignment_form.html'
    
    def test_func(self):
        user = self.request.user
        if is_admin(user):
            return True
        
        if is_teacher(user):
            assignment = self.get_object()
            return assignment.class_assignment.teacher == user.teacher
        
        return False
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.object
        
        # Add class information for the template
        if assignment.class_assignment:
            context['selected_class'] = assignment.class_assignment.get_class_level_display()
            context['selected_subject'] = assignment.subject
            context['selected_teacher'] = assignment.class_assignment.teacher
            context['academic_year'] = assignment.class_assignment.academic_year
        
        # Add user role flags
        context['is_admin'] = is_admin(self.request.user)
        context['is_teacher'] = is_teacher(self.request.user)
        
        return context
    
    def form_valid(self, form):
        # Check if due date was changed (important change)
        old_assignment = Assignment.objects.get(pk=self.object.pk)
        new_due_date = form.cleaned_data.get('due_date')
        
        messages.success(self.request, 'Assignment updated successfully!')
        response = super().form_valid(form)
        
        # Send notification if due date was changed
        if old_assignment.due_date != new_due_date:
            self.send_due_date_update_notifications(old_assignment.due_date)
            
        return response
    
    def send_due_date_update_notifications(self, old_due_date):
        """Send notifications if due date was changed"""
        assignment = self.object
        
        try:
            from core.models import Student
            students = Student.objects.filter(class_level=assignment.class_assignment.class_level)
            
            for student in students:
                from core.views.notifications_views import create_notification
                create_notification(
                    recipient=student.user,
                    title="Assignment Due Date Updated",
                    message=f"Due date for '{assignment.title}' has been changed from {old_due_date.strftime('%b %d, %Y')} to {assignment.due_date.strftime('%b %d, %Y')}",
                    notification_type="ASSIGNMENT",
                    link=reverse('assignment_detail', kwargs={'pk': assignment.pk})
                )
            
            print(f"DEBUG: Sent due date update notifications to {students.count()} students")
            
        except Exception as e:
            print(f"ERROR: Failed to send due date update notifications: {str(e)}")
    
    def get_success_url(self):
        return reverse_lazy('assignment_detail', kwargs={'pk': self.object.pk})


class AssignmentDeleteView(LoginRequiredMixin, UserPassesTestMixin, TeacherOwnershipRequiredMixin, DeleteView):
    model = Assignment
    template_name = 'core/academics/assignments/assignment_confirm_delete.html'
    success_url = reverse_lazy('assignment_list')
    
    def test_func(self):
        user = self.request.user
        return is_admin(user) or is_teacher(user)
    
    def delete(self, request, *args, **kwargs):
        assignment = self.get_object()
        
        # Delete associated analytics
        try:
            AssignmentAnalytics.objects.filter(assignment=assignment).delete()
        except Exception as e:
            logger.error(f"Error deleting analytics for assignment {assignment.id}: {str(e)}")
        
        messages.success(request, 'Assignment deleted successfully!')
        return super().delete(request, *args, **kwargs)


class GradeAssignmentView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to grade a student's assignment submission - supports both HTML and AJAX."""
    
    def get_student_assignment(self):
        """Get student assignment object from any possible parameter"""
        # Try all possible parameter names
        student_assignment_id = (
            self.kwargs.get('student_assignment_id') or 
            self.kwargs.get('pk') or 
            self.kwargs.get('id')
        )
        
        if not student_assignment_id:
            logger.error(f"No student assignment ID found in kwargs: {self.kwargs}")
            raise Http404("Student assignment ID not provided")
        
        try:
            return get_object_or_404(StudentAssignment, id=student_assignment_id)
        except StudentAssignment.DoesNotExist:
            logger.error(f"StudentAssignment with ID {student_assignment_id} does not exist")
            raise Http404("Student assignment not found")
        except ValueError:
            logger.error(f"Invalid student assignment ID: {student_assignment_id}")
            raise Http404("Invalid student assignment ID")

    def test_func(self):
        try:
            self.student_assignment = self.get_student_assignment()
            
            # Allow admins to grade any assignment
            if is_admin(self.request.user):
                return True
                
            # Check if user is a teacher and owns the assignment
            if is_teacher(self.request.user):
                return self.student_assignment.assignment.class_assignment.teacher == self.request.user.teacher
            
            return False
            
        except Http404:
            raise
        except Exception as e:
            logger.error(f"Error in test_func for GradeAssignmentView: {str(e)}")
            return False

    def get(self, request, *args, **kwargs):
        """Return HTML form for grading or JSON data for AJAX requests"""
        try:
            if not hasattr(self, 'student_assignment'):
                self.student_assignment = self.get_student_assignment()

            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Return JSON for AJAX requests
                graded_date = None
                if self.student_assignment.status == 'GRADED':
                    if self.student_assignment.submitted_date:
                        graded_date = self.student_assignment.submitted_date.strftime("%b. %d, %Y")
                    else:
                        graded_date = "Recently graded"
                
                return JsonResponse({
                    'success': True,
                    'score': float(self.student_assignment.score) if self.student_assignment.score else None,
                    'feedback': self.student_assignment.feedback,
                    'max_score': self.student_assignment.assignment.max_score,
                    'status': self.student_assignment.status,
                    'graded_date': graded_date,
                    'submitted_date': self.student_assignment.submitted_date.strftime("%b. %d, %Y") if self.student_assignment.submitted_date else None,
                    'is_late': self.student_assignment.is_late(),
                    'debug': {
                        'student_assignment_id': self.student_assignment.id,
                        'assignment_id': self.student_assignment.assignment.id
                    }
                })
            else:
                # Return HTML template for regular browser requests
                context = {
                    'student_assignment': self.student_assignment,
                    'assignment': self.student_assignment.assignment,
                    'student': self.student_assignment.student,
                    'max_score': self.student_assignment.assignment.max_score,
                    'is_late': self.student_assignment.is_late(),
                    'submitted_date': self.student_assignment.submitted_date,
                }
                return render(request, 'core/academics/assignments/grade_assignment.html', context)
                
        except Exception as e:
            logger.error(f"Error in GradeAssignmentView GET: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})
            else:
                messages.error(request, f"Error loading grading form: {str(e)}")
                return redirect('assignment_detail', pk=self.student_assignment.assignment.pk)

    def post(self, request, *args, **kwargs):
        """Handle form submission for both AJAX and regular requests"""
        try:
            if not hasattr(self, 'student_assignment'):
                self.student_assignment = self.get_student_assignment()
            
            grade = request.POST.get('grade') or request.POST.get('score')
            feedback = request.POST.get('feedback', '')
            
            # Validate grade
            if grade and grade.strip():
                try:
                    grade_value = float(grade)
                    if grade_value < 0 or grade_value > self.student_assignment.assignment.max_score:
                        error_msg = f'Score must be between 0 and {self.student_assignment.assignment.max_score}'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({'success': False, 'error': error_msg})
                        else:
                            messages.error(request, error_msg)
                            return self.render_form_with_errors(request, grade, feedback)
                except ValueError:
                    error_msg = 'Invalid score format'
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': error_msg})
                    else:
                        messages.error(request, error_msg)
                        return self.render_form_with_errors(request, grade, feedback)
            else:
                error_msg = 'Score is required'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': error_msg})
                else:
                    messages.error(request, error_msg)
                    return self.render_form_with_errors(request, grade, feedback)
            
            # Store old status for notification logic
            old_status = self.student_assignment.status
            
            # Update the student assignment
            self.student_assignment.score = grade_value
            self.student_assignment.feedback = feedback
            self.student_assignment.status = 'GRADED'
            
            # Set graded date
            self.student_assignment.graded_date = timezone.now()
            
            # Ensure submitted_date is set (if not already set)
            if not self.student_assignment.submitted_date:
                self.student_assignment.submitted_date = timezone.now()
                
            self.student_assignment.save()

            # Update analytics
            try:
                self.student_assignment.assignment.update_analytics()
            except Exception as e:
                logger.error(f"Error updating analytics after grading: {str(e)}")

            # Send grading notification to student
            self.send_grading_notification(old_status)

            # Handle response based on request type
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # AJAX response
                response_data = {
                    'success': True, 
                    'grade': grade_value, 
                    'feedback': feedback,
                    'status': 'GRADED',
                    'graded_date': self.student_assignment.graded_date.strftime("%b. %d, %Y at %I:%M %p")
                }
                
                # Add dates to response
                if self.student_assignment.submitted_date:
                    response_data['submitted_date'] = self.student_assignment.submitted_date.strftime("%b. %d, %Y")
                else:
                    response_data['graded_date'] = 'Just now'
                
                return JsonResponse(response_data)
            else:
                # Regular form submission - redirect with success message
                messages.success(request, f'Assignment graded successfully for {self.student_assignment.student.get_full_name()}')
                return redirect('assignment_detail', pk=self.student_assignment.assignment.pk)
            
        except Exception as e:
            logger.error(f"Error in GradeAssignmentView POST: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})
            else:
                messages.error(request, f"Error grading assignment: {str(e)}")
                return redirect('assignment_detail', pk=self.student_assignment.assignment.pk)

    def render_form_with_errors(self, request, grade, feedback):
        """Render the form again with the submitted data and error messages"""
        context = {
            'student_assignment': self.student_assignment,
            'assignment': self.student_assignment.assignment,
            'student': self.student_assignment.student,
            'max_score': self.student_assignment.assignment.max_score,
            'is_late': self.student_assignment.is_late(),
            'submitted_date': self.student_assignment.submitted_date,
            'submitted_grade': grade,
            'submitted_feedback': feedback,
        }
        return render(request, 'core/academics/assignments/grade_assignment.html', context)

    def send_grading_notification(self, old_status):
        """
        Send notification to student when their assignment is graded
        """
        try:
            from core.views.notifications_views import create_notification
            from django.urls import reverse
            
            assignment = self.student_assignment.assignment
            student = self.student_assignment.student
            
            # Only send notification if the assignment was just graded (status changed to GRADED)
            if old_status != 'GRADED':
                # Calculate percentage score
                percentage = (self.student_assignment.score / assignment.max_score) * 100
                
                # Determine performance message based on score
                if percentage >= 80:
                    performance_msg = "Excellent work!"
                elif percentage >= 70:
                    performance_msg = "Good job!"
                elif percentage >= 50:
                    performance_msg = "Satisfactory performance."
                else:
                    performance_msg = "Needs improvement."
                
                # Create the notification
                create_notification(
                    recipient=student.user,
                    title="Assignment Graded",
                    message=(
                        f"Your assignment '{assignment.title}' has been graded. "
                        f"Score: {self.student_assignment.score}/{assignment.max_score} ({percentage:.1f}%). "
                        f"{performance_msg}"
                    ),
                    notification_type="GRADE",
                    link=reverse('assignment_detail', kwargs={'pk': assignment.pk})
                )
                
                logger.info(
                    f"Grading notification sent to {student.user.username} "
                    f"for assignment '{assignment.title}' - Score: {self.student_assignment.score}/{assignment.max_score}"
                )
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to send grading notification: {str(e)}")
            return False


class SubmitAssignmentView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = StudentAssignment
    form_class = StudentAssignmentSubmissionForm
    template_name = 'core/academics/assignments/submit_assignment.html'

    def test_func(self):
        # FIX: Ensure student can only submit their own assignments
        student_assignment = self.get_object()
        return is_student(self.request.user) and student_assignment.student == self.request.user.student

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['assignment'] = self.object.assignment
        return kwargs

    def form_valid(self, form):
        # Set submitted date when form is valid
        self.object.submitted_date = timezone.now()
        messages.success(self.request, 'Assignment submitted successfully!')
        response = super().form_valid(form)
        
        # Update analytics
        try:
            self.object.assignment.update_analytics()
        except Exception as e:
            logger.error(f"Error updating analytics after submission: {str(e)}")
            
        return response

    def get_success_url(self):
        return reverse_lazy('assignment_detail', kwargs={'pk': self.object.assignment.pk})


class AssignmentCalendarView(LoginRequiredMixin, TemplateView):
    template_name = 'core/academics/assignments/assignment_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get year and month from URL parameters, default to current
        now = timezone.now()
        year = int(self.kwargs.get('year', now.year))
        month = int(self.kwargs.get('month', now.month))
        context['month'] = month
        context['year'] = year
        
        # Add user role information for template
        context['is_teacher'] = is_teacher(self.request.user)
        context['is_student'] = is_student(self.request.user)
        context['is_admin'] = is_admin(self.request.user)
        
        return context


class AssignmentEventJsonView(LoginRequiredMixin, View):
    """ENHANCED JSON endpoint for calendar events with color coding by status"""
    
    def get(self, request, *args, **kwargs):
        start = request.GET.get('start')
        end = request.GET.get('end')

        # Convert to date objects using datetime module
        if start:
            start_date = datetime.datetime.fromisoformat(start.replace('Z', '+00:00')).date()
        else:
            start_date = None
            
        if end:
            end_date = datetime.datetime.fromisoformat(end.replace('Z', '+00:00')).date()
        else:
            end_date = None

        # ENHANCED: Different data based on user role
        if is_student(request.user):
            # For students, use StudentAssignment to get status-based colors
            student = request.user.student
            student_assignments = StudentAssignment.objects.filter(
                student=student
            ).select_related('assignment', 'assignment__subject')
            
            # Filter by date range for the calendar
            if start_date and end_date:
                student_assignments = student_assignments.filter(
                    assignment__due_date__date__gte=start_date, 
                    assignment__due_date__date__lte=end_date
                )

            events = []
            for sa in student_assignments:
                color = self.get_assignment_color(sa)
                events.append({
                    'title': sa.assignment.title,
                    'start': sa.assignment.due_date.isoformat(),
                    'end': sa.assignment.due_date.isoformat(),
                    'color': color,
                    'textColor': 'white' if color in ['#dc3545', '#28a745', '#007bff'] else 'black',
                    'url': reverse('assignment_detail', kwargs={'pk': sa.assignment.pk}),
                    'extendedProps': {
                        'subject': sa.assignment.subject.name,
                        'type': sa.assignment.get_assignment_type_display(),
                        'status': sa.status,
                        'status_display': sa.get_status_display(),
                        'is_overdue': sa.assignment.due_date < timezone.now(),
                        'can_submit': sa.status in ['PENDING', 'LATE'],
                        'score': float(sa.score) if sa.score else None,
                    }
                })
                
        else:
            # For teachers/admins, show all assignments
            queryset = Assignment.objects.all()
            
            # Apply user filters
            if is_teacher(request.user):
                queryset = queryset.filter(class_assignment__teacher=request.user.teacher)
            
            # Filter by date range for the calendar
            if start_date and end_date:
                queryset = queryset.filter(due_date__date__gte=start_date, due_date__date__lte=end_date)

            events = []
            for assignment in queryset:
                # For teachers, color based on submission status
                submission_stats = assignment.get_quick_stats()
                color = self.get_teacher_assignment_color(assignment, submission_stats)
                
                events.append({
                    'title': assignment.title,
                    'start': assignment.due_date.isoformat(),
                    'end': assignment.due_date.isoformat(),
                    'color': color,
                    'textColor': 'white',
                    'url': reverse('assignment_detail', kwargs={'pk': assignment.pk}),
                    'extendedProps': {
                        'subject': assignment.subject.name,
                        'type': assignment.get_assignment_type_display(),
                        'class_level': assignment.class_assignment.get_class_level_display(),
                        'total_students': submission_stats['total_students'],
                        'submitted_count': submission_stats['submitted'],
                        'graded_count': submission_stats['graded'],
                        'submission_rate': round((submission_stats['submitted'] / submission_stats['total_students'] * 100) if submission_stats['total_students'] > 0 else 0, 1),
                    }
                })
        
        return JsonResponse(events, safe=False)
    
    def get_assignment_color(self, student_assignment):
        """Get color based on assignment status and urgency for students"""
        now = timezone.now()
        due_date = student_assignment.assignment.due_date
        
        if student_assignment.status == 'GRADED':
            return '#28a745'  # Green - graded
        elif student_assignment.status == 'SUBMITTED':
            return '#17a2b8'  # Blue - submitted but not graded
        elif student_assignment.status == 'LATE':
            return '#dc3545'  # Red - late submission
        elif due_date < now:
            return '#dc3545'  # Red - overdue and not submitted
        elif (due_date - now).days <= 1:
            return '#ffc107'  # Yellow - due very soon (1 day)
        elif (due_date - now).days <= 3:
            return '#fd7e14'  # Orange - due soon (3 days)
        else:
            return '#007bff'  # Blue - normal (more than 3 days)
    
    def get_teacher_assignment_color(self, assignment, submission_stats):
        """Get color based on submission statistics for teachers"""
        now = timezone.now()
        
        if assignment.due_date < now:
            if submission_stats['submitted'] == submission_stats['total_students']:
                return '#28a745'  # Green - all submitted (past due)
            elif submission_stats['submitted'] >= submission_stats['total_students'] * 0.8:
                return '#17a2b8'  # Blue - good submission rate (past due)
            else:
                return '#dc3545'  # Red - poor submission rate (past due)
        else:
            # Assignment not yet due
            if submission_stats['submitted'] == submission_stats['total_students']:
                return '#20c997'  # Teal - all submitted early
            elif submission_stats['submitted'] >= submission_stats['total_students'] * 0.5:
                return '#007bff'  # Blue - good progress
            else:
                return '#6c757d'  # Gray - low submission rate


class BulkGradeAssignmentView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Bulk grade multiple student assignments at once"""
    
    def test_func(self):
        assignment_id = self.kwargs.get('pk')
        assignment = get_object_or_404(Assignment, id=assignment_id)
        return is_teacher(self.request.user) and assignment.class_assignment.teacher == self.request.user.teacher
    
    def post(self, request, *args, **kwargs):
        try:
            assignment = get_object_or_404(Assignment, id=self.kwargs.get('pk'))
            grades_data = request.POST.get('grades_data', '{}')
            grades_dict = json.loads(grades_data)
            
            updated_count = 0
            for student_id, grade_data in grades_dict.items():
                try:
                    student_assignment = StudentAssignment.objects.get(
                        assignment=assignment,
                        student_id=student_id
                    )
                    
                    if 'score' in grade_data:
                        student_assignment.score = grade_data['score']
                    if 'feedback' in grade_data:
                        student_assignment.feedback = grade_data['feedback']
                    
                    student_assignment.status = 'GRADED'
                    student_assignment.graded_date = timezone.now()
                    student_assignment.save()
                    updated_count += 1
                    
                except (StudentAssignment.DoesNotExist, ValueError):
                    continue
            
            # Update analytics after bulk grading
            try:
                assignment.update_analytics()
            except Exception as e:
                logger.error(f"Error updating analytics after bulk grading: {str(e)}")
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully graded {updated_count} assignments',
                'updated_count': updated_count
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class AssignmentAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Detailed analytics view for an assignment"""
    model = Assignment
    template_name = 'core/academics/assignments/assignment_analytics.html'
    
    def test_func(self):
        assignment = self.get_object()
        if is_admin(self.request.user):
            return True
        if is_teacher(self.request.user):
            return assignment.class_assignment.teacher == self.request.user.teacher
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.object
        
        # Get analytics data
        try:
            analytics = assignment.get_analytics(recalculate=True)
            context['analytics'] = analytics
            
            # Get detailed student performance data
            student_assignments = assignment.student_assignments.select_related('student').all()
            
            # Performance distribution
            performance_data = {
                'excellent': student_assignments.filter(score__gte=80).count(),
                'good': student_assignments.filter(score__gte=70, score__lt=80).count(),
                'average': student_assignments.filter(score__gte=50, score__lt=70).count(),
                'poor': student_assignments.filter(score__lt=50).count(),
                'ungraded': student_assignments.filter(score__isnull=True).count()
            }
            
            context['performance_data'] = performance_data
            context['student_assignments'] = student_assignments
            
        except Exception as e:
            logger.error(f"Error getting detailed analytics for assignment {assignment.id}: {str(e)}")
            context['analytics'] = None
        
        return context


class AssignmentExportView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Export assignment data to CSV"""
    
    def test_func(self):
        assignment_id = self.kwargs.get('pk')
        assignment = get_object_or_404(Assignment, id=assignment_id)
        if is_admin(self.request.user):
            return True
        if is_teacher(self.request.user):
            return assignment.class_assignment.teacher == self.request.user.teacher
        return False
    
    def get(self, request, *args, **kwargs):
        import csv
        from django.http import HttpResponse
        
        assignment = get_object_or_404(Assignment, id=self.kwargs.get('pk'))
        student_assignments = assignment.student_assignments.select_related('student').all()
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="assignment_{assignment.id}_grades.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Student ID', 'Student Name', 'Status', 'Score', 'Submitted Date', 'Graded Date', 'Feedback'])
        
        for sa in student_assignments:
            writer.writerow([
                sa.student.student_id,
                sa.student.get_full_name(),
                sa.get_status_display(),
                sa.score or 'Not Graded',
                sa.submitted_date.strftime('%Y-%m-%d %H:%M') if sa.submitted_date else 'Not Submitted',
                sa.graded_date.strftime('%Y-%m-%d %H:%M') if sa.graded_date else 'Not Graded',
                sa.feedback or 'No feedback'
            ])
        
        return response