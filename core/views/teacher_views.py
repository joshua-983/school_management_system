"""
Teacher management views for the school management system.
"""
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta

from core.utils import is_admin, is_teacher
from ..models import Teacher, Assignment, StudentAssignment, ClassAssignment, Subject
from ..forms import TeacherRegistrationForm
from django.contrib.auth import get_user_model


class TeacherListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Teacher
    template_name = 'core/hr/teacher_list.html'
    context_object_name = 'teachers'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print(f"DEBUG: {context['teachers'].count()} teachers in context")
        for teacher in context['teachers']:
            print(f"DEBUG: Teacher {teacher.id} - User: {teacher.user}")
            if teacher.user:
                print(f"DEBUG: -> Name: '{teacher.user.get_full_name()}', Email: '{teacher.user.email}'")
        return context


class TeacherCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Teacher
    form_class = TeacherRegistrationForm
    template_name = 'core/hr/teacher_form.html'
    success_url = reverse_lazy('teacher_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        try:
            # Check if teacher with this email already exists
            email = form.cleaned_data.get('email')
            User = get_user_model()
            
            if User.objects.filter(email=email).exists():
                form.add_error('email', 'A teacher with this email already exists.')
                return self.form_invalid(form)
            
            # Save the form (this will create both user and teacher)
            teacher = form.save()
            
            messages.success(self.request, f'Teacher {teacher.user.get_full_name()} created successfully!')
            return super().form_valid(form)
            
        except Exception as e:
            print(f"DEBUG: Error creating teacher - {str(e)}")
            error_message = f'Error creating teacher: {str(e)}'
            if 'email' in str(e).lower():
                error_message = 'Email already exists or is invalid. Please use a different email.'
            elif 'username' in str(e).lower():
                error_message = 'Username already exists. Please choose a different username.'
                
            messages.error(self.request, error_message)
            return self.form_invalid(form)


class TeacherUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Teacher
    form_class = TeacherRegistrationForm
    template_name = 'core/hr/teacher_form.html'
    success_url = reverse_lazy('teacher_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Teacher updated successfully')
        return super().form_valid(form)


class TeacherDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Teacher
    template_name = 'core/hr/teacher_confirm_delete.html'
    success_url = reverse_lazy('teacher_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Teacher deleted successfully')
        return super().delete(request, *args, **kwargs)


# Enhanced Teacher Analytics Views
class TeacherAssignmentAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/academics/assignments/teacher_analytics.html'
    
    def test_func(self):
        return is_teacher(self.request.user) or is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if is_teacher(self.request.user):
            teacher = self.request.user.teacher
            context['current_teacher'] = teacher
        else:
            # Admin viewing specific teacher
            teacher_id = self.kwargs.get('teacher_id')
            if teacher_id:
                teacher = Teacher.objects.get(id=teacher_id)
                context['current_teacher'] = teacher
            else:
                # Admin overview of all teachers
                context['all_teachers'] = True
        
        if 'current_teacher' in context:
            teacher = context['current_teacher']
            
            # Get all assignments for this teacher
            assignments = Assignment.objects.filter(
                class_assignment__teacher=teacher
            ).select_related(
                'subject', 'class_assignment'
            ).prefetch_related('student_assignments')
            
            # Calculate comprehensive statistics
            context.update(self.get_teacher_analytics(teacher, assignments))
            
        elif 'all_teachers' in context:
            # Admin view - show analytics for all teachers
            context.update(self.get_all_teachers_analytics())
        
        return context
    
    def get_teacher_analytics(self, teacher, assignments):
        """Get comprehensive analytics for a specific teacher"""
        analytics = {}
        
        # Basic counts
        analytics['total_assignments'] = assignments.count()
        analytics['active_assignments'] = assignments.filter(due_date__gte=timezone.now()).count()
        analytics['completed_assignments'] = assignments.filter(due_date__lt=timezone.now()).count()
        
        # Student assignment statistics
        student_assignments = StudentAssignment.objects.filter(
            assignment__class_assignment__teacher=teacher
        )
        
        analytics['total_student_assignments'] = student_assignments.count()
        analytics['graded_count'] = student_assignments.filter(status='GRADED').count()
        analytics['pending_count'] = student_assignments.filter(status='PENDING').count()
        analytics['submitted_count'] = student_assignments.filter(status__in=['SUBMITTED', 'LATE']).count()
        
        # Performance metrics
        analytics['average_submission_rate'] = self.calculate_average_submission_rate(assignments)
        analytics['average_score'] = self.calculate_average_score(assignments)
        analytics['average_grading_time'] = self.calculate_average_grading_time(teacher)
        
        # Recent activity
        analytics['recent_assignments'] = assignments.order_by('-created_at')[:5]
        analytics['upcoming_deadlines'] = assignments.filter(
            due_date__gte=timezone.now()
        ).order_by('due_date')[:5]
        
        # Subject-wise performance
        analytics['subject_performance'] = self.get_subject_performance(assignments)
        
        # Class-wise distribution
        analytics['class_distribution'] = self.get_class_distribution(assignments)
        
        # Timeline data for charts
        analytics['timeline_data'] = self.get_timeline_data(teacher)
        
        return analytics
    
    def get_all_teachers_analytics(self):
        """Get analytics overview for all teachers (admin view)"""
        analytics = {}
        
        teachers = Teacher.objects.filter(is_active=True)
        analytics['total_teachers'] = teachers.count()
        analytics['active_teachers'] = teachers.filter(
            classassignment__assignment__due_date__gte=timezone.now()
        ).distinct().count()
        
        # Teacher performance metrics
        teacher_stats = []
        for teacher in teachers:
            assignments = Assignment.objects.filter(class_assignment__teacher=teacher)
            if assignments.exists():
                stats = {
                    'teacher': teacher,
                    'total_assignments': assignments.count(),
                    'average_submission_rate': self.calculate_average_submission_rate(assignments),
                    'average_score': self.calculate_average_score(assignments),
                }
                teacher_stats.append(stats)
        
        analytics['teacher_stats'] = sorted(
            teacher_stats, 
            key=lambda x: x['total_assignments'], 
            reverse=True
        )
        
        return analytics
    
    def calculate_average_submission_rate(self, assignments):
        total_rate = 0
        count = 0
        for assignment in assignments:
            analytics = assignment.get_analytics()
            if analytics and analytics.submission_rate:
                total_rate += analytics.submission_rate
                count += 1
        return round(total_rate / count, 2) if count > 0 else 0
    
    def calculate_average_score(self, assignments):
        total_score = 0
        count = 0
        for assignment in assignments:
            analytics = assignment.get_analytics()
            if analytics and analytics.average_score:
                total_score += float(analytics.average_score)
                count += 1
        return round(total_score / count, 2) if count > 0 else 0
    
    def calculate_average_grading_time(self, teacher):
        """Calculate average time between submission and grading"""
        graded_assignments = StudentAssignment.objects.filter(
            assignment__class_assignment__teacher=teacher,
            status='GRADED',
            submitted_date__isnull=False
        ).exclude(submitted_date__isnull=True)
        
        total_days = 0
        count = 0
        
        for sa in graded_assignments:
            if sa.submitted_date:
                # Use created_at as grading time approximation
                grading_time = (sa.updated_at - sa.submitted_date).days
                total_days += grading_time
                count += 1
        
        return round(total_days / count, 1) if count > 0 else 0
    
    def get_subject_performance(self, assignments):
        """Get performance metrics by subject"""
        subjects = Subject.objects.filter(
            classassignment__assignment__in=assignments
        ).distinct()
        
        subject_data = []
        for subject in subjects:
            subject_assignments = assignments.filter(subject=subject)
            avg_score = self.calculate_average_score(subject_assignments)
            avg_submission_rate = self.calculate_average_submission_rate(subject_assignments)
            
            subject_data.append({
                'subject': subject,
                'assignment_count': subject_assignments.count(),
                'average_score': avg_score,
                'submission_rate': avg_submission_rate,
            })
        
        return sorted(subject_data, key=lambda x: x['assignment_count'], reverse=True)
    
    def get_class_distribution(self, assignments):
        """Get assignment distribution by class level"""
        from ..models import CLASS_LEVEL_CHOICES
        
        class_data = []
        for class_level, display_name in CLASS_LEVEL_CHOICES:
            class_assignments = assignments.filter(
                class_assignment__class_level=class_level
            )
            if class_assignments.exists():
                class_data.append({
                    'class_level': class_level,
                    'display_name': display_name,
                    'assignment_count': class_assignments.count(),
                    'average_score': self.calculate_average_score(class_assignments),
                })
        
        return sorted(class_data, key=lambda x: x['assignment_count'], reverse=True)
    
    def get_timeline_data(self, teacher):
        """Get data for timeline charts"""
        # Last 6 months of assignment data
        six_months_ago = timezone.now() - timedelta(days=180)
        
        monthly_data = []
        for i in range(6):
            month_start = timezone.now() - timedelta(days=30 * (5 - i))
            month_end = month_start + timedelta(days=30)
            
            month_assignments = Assignment.objects.filter(
                class_assignment__teacher=teacher,
                created_at__range=[month_start, month_end]
            )
            
            monthly_data.append({
                'month': month_start.strftime('%b %Y'),
                'assignments_created': month_assignments.count(),
                'average_submission_rate': self.calculate_average_submission_rate(month_assignments),
            })
        
        return monthly_data


class TeacherDetailAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Detailed analytics for a specific teacher"""
    model = Teacher
    template_name = 'core/hr/teacher_analytics_detail.html'
    context_object_name = 'teacher'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.object
        
        # Get all assignments for this teacher
        assignments = Assignment.objects.filter(
            class_assignment__teacher=teacher
        ).select_related('subject', 'class_assignment')
        
        # Comprehensive analytics
        context['total_assignments'] = assignments.count()
        context['recent_assignments'] = assignments.order_by('-created_at')[:10]
        
        # Student performance data
        student_assignments = StudentAssignment.objects.filter(
            assignment__class_assignment__teacher=teacher
        )
        
        context['grading_stats'] = {
            'total': student_assignments.count(),
            'graded': student_assignments.filter(status='GRADED').count(),
            'pending': student_assignments.filter(status='PENDING').count(),
            'submitted': student_assignments.filter(status__in=['SUBMITTED', 'LATE']).count(),
        }
        
        return context