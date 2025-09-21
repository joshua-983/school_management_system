# core/academics/views/assignment_views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.core.files.storage import default_storage
import datetime
import json
import logging

from ..models import Assignment, StudentAssignment, ClassAssignment, Subject, Student, CLASS_LEVEL_CHOICES, AssignmentAnalytics
from .base_views import is_admin, is_teacher, is_student
from ..forms import AssignmentForm, StudentAssignmentForm

logger = logging.getLogger(__name__)

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
        
        # User-specific filtering
        if is_teacher(self.request.user):
            queryset = queryset.filter(class_assignment__teacher=self.request.user.teacher)
        elif is_student(self.request.user):
            # Get the student's class level and filter assignments for that level
            student_class_level = self.request.user.student.class_level
            queryset = queryset.filter(class_assignment__class_level=student_class_level)
            
            # Ensure student can only see their own assignments with proper relationship
            queryset = queryset.filter(
                student_assignments__student=self.request.user.student
            )
        
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

# In assignment_views.py - Update AssignmentCreateView
class AssignmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Assignment
    form_class = AssignmentForm
    template_name = 'core/academics/assignments/assignment_form.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        try:
            # This will call our custom save method
            return super().form_valid(form)
        except ValidationError as e:
            # Handle validation errors from the model
            form.add_error(None, str(e))
            return self.form_invalid(form)
        except Exception as e:
            # Handle other errors
            logger.error(f"Error creating assignment: {str(e)}")
            form.add_error(None, f"Error creating assignment: {str(e)}")
            return self.form_invalid(form)
    def get_success_url(self):
        return reverse_lazy('assignment_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add class levels to context
        context['class_levels'] = CLASS_LEVEL_CHOICES
        
        # Add available classes for the current teacher
        if is_teacher(self.request.user):
            context['available_classes'] = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            )
        else:  # Admin
            context['available_classes'] = ClassAssignment.objects.all()
            
        return context
    
    def form_invalid(self, form):
        # Log form errors for debugging
        logger.error(f"Form errors: {form.errors}")
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)
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
        
        # This data is now available without causing extra database hits
        student_assignments = assignment.student_assignments.all()
        context['student_assignments'] = student_assignments
        
        # Add counts for the detail page
        context['submitted_count'] = student_assignments.exclude(status='PENDING').count()
        context['graded_count'] = student_assignments.filter(status='GRADED').count()
        
        # Get analytics data
        try:
            analytics = assignment.get_analytics()
            context['analytics'] = analytics
        except Exception as e:
            logger.error(f"Error getting analytics for assignment {assignment.id}: {str(e)}")
            context['analytics'] = None
        
        # Permission check for editing - use functions from base_views
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
        # Use the functions from base_views
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
    
    def form_valid(self, form):
        messages.success(self.request, 'Assignment updated successfully!')
        return super().form_valid(form)
    
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
    """AJAX view to grade a student's assignment submission."""
    
    def test_func(self):
        # Ensure the user is a teacher and owns the assignment
        student_assignment_id = self.kwargs.get('pk')
        self.student_assignment = get_object_or_404(StudentAssignment, id=student_assignment_id)
        return is_teacher(self.request.user) and self.student_assignment.assignment.class_assignment.teacher == self.request.user.teacher

    def post(self, request, *args, **kwargs):
        try:
            grade = request.POST.get('grade')
            feedback = request.POST.get('feedback', '')
            self.student_assignment.grade = grade
            self.student_assignment.feedback = feedback
            self.student_assignment.status = 'GRADED'
            self.student_assignment.graded_date = timezone.now()
            self.student_assignment.save()

            # Update analytics
            try:
                self.student_assignment.assignment.update_analytics()
            except Exception as e:
                logger.error(f"Error updating analytics after grading: {str(e)}")

            return JsonResponse({
                'success': True, 
                'grade': grade, 
                'graded_date': self.student_assignment.graded_date.strftime("%b. %d, %Y"),
                'feedback': feedback
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

class SubmitAssignmentView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = StudentAssignment
    form_class = StudentAssignmentForm
    template_name = 'core/academics/assignments/submit_assignment.html'

    def test_func(self):
        # Ensure the current user is the student linked to this StudentAssignment
        student_assignment = self.get_object()
        return is_student(self.request.user) and student_assignment.student == self.request.user.student

    def form_valid(self, form):
        form.instance.status = 'SUBMITTED'
        form.instance.submitted_date = timezone.now()
        
        # Update analytics
        try:
            form.instance.assignment.update_analytics()
        except Exception as e:
            logger.error(f"Error updating analytics after submission: {str(e)}")
            
        messages.success(self.request, 'Assignment submitted successfully!')
        return super().form_valid(form)

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
        return context

class AssignmentEventJsonView(LoginRequiredMixin, View):
    """JSON endpoint for calendar events."""
    
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

        queryset = Assignment.objects.all()
        # Apply user filters (same logic as your ListView)
        if is_teacher(request.user):
            queryset = queryset.filter(class_assignment__teacher=request.user.teacher)
        elif is_student(request.user):
            queryset = queryset.filter(class_assignment__class_level=request.user.student.class_level)

        # Filter by date range for the calendar
        if start_date and end_date:
            queryset = queryset.filter(due_date__date__gte=start_date, due_date__date__lte=end_date)

        events = []
        for assignment in queryset:
            events.append({
                'title': assignment.title,
                'start': assignment.due_date.isoformat(),
                'end': assignment.due_date.isoformat(),
                'url': reverse('assignment_detail', kwargs={'pk': assignment.pk}),
                'color': 'red' if assignment.due_date < timezone.now() else '#3a87ad',
                'extendedProps': {
                    'subject': assignment.subject.name,
                    'type': assignment.get_assignment_type_display(),
                }
            })
        return JsonResponse(events, safe=False)

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