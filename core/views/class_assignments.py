from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect
from django.db.models import Count, Q
from django.core.exceptions import PermissionDenied
import csv
import datetime
from openpyxl import Workbook

from ..models import ClassAssignment, Student, Subject, Teacher, CLASS_LEVEL_CHOICES, AuditLog
from ..forms import ClassAssignmentForm
from ..utils import is_admin, is_teacher

# Class Assignment Views
class ClassAssignmentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ClassAssignment
    template_name = 'core/academics/classes/class_assignment_list.html'
    context_object_name = 'class_assignments'
    paginate_by = 20
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('teacher', 'subject', 'teacher__user')
        
        # Filter by user role
        if is_teacher(self.request.user):
            queryset = queryset.filter(teacher=self.request.user.teacher)
        
        # Apply filters from GET parameters
        class_level = self.request.GET.get('class_level')
        if class_level:
            queryset = queryset.filter(class_level=class_level)
        
        academic_year = self.request.GET.get('academic_year')
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        
        # Subject filter
        subject_id = self.request.GET.get('subject')
        if subject_id:
            try:
                subject_id_int = int(subject_id)
                queryset = queryset.filter(subject_id=subject_id_int)
            except (ValueError, TypeError):
                # If conversion fails, skip this filter
                pass
        
        # Status filter
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        # Search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(teacher__user__first_name__icontains=search) |
                Q(teacher__user__last_name__icontains=search) |
                Q(subject__name__icontains=search) |
                Q(subject__code__icontains=search) |
                Q(class_level__icontains=search)
            )
        
        # Only show active by default for non-admins
        if not is_admin(self.request.user) and 'is_active' not in self.request.GET:
            queryset = queryset.filter(is_active=True)
        
        return queryset.order_by('class_level', 'subject__name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter data
        context['class_levels'] = CLASS_LEVEL_CHOICES
        
        # DEBUG: Let's see what's happening with subjects
        print("=" * 50)
        print("DEBUG: Subject Information")
        print("=" * 50)
        
        # Get all active subjects
        all_subjects = Subject.objects.filter(is_active=True)
        print(f"Total active subjects in database: {all_subjects.count()}")
        
        # List all subjects
        for subject in all_subjects:
            print(f"Subject: {subject.name} (ID: {subject.id}, Code: {subject.code})")
        
        # Get subjects with assignment counts using correct reverse relation
        subjects_with_counts = Subject.objects.filter(is_active=True).annotate(
            assignment_count=Count('classassignment')
        ).order_by('name')
        
        print(f"\nSubjects with assignment counts: {subjects_with_counts.count()}")
        for subject in subjects_with_counts:
            print(f"{subject.name}: {subject.assignment_count} assignments")
        
        context['subjects'] = subjects_with_counts
        
        # Add statistics - FIXED
        total_assignments = ClassAssignment.objects.count()
        context['total_assignments'] = total_assignments
        
        active_teachers = Teacher.objects.filter(is_active=True).count()
        context['active_teachers'] = active_teachers
        
        # Count of all active subjects
        total_subjects = Subject.objects.filter(is_active=True).count()
        context['total_subjects'] = total_subjects
        
        # Count assigned subjects (subjects with at least one assignment)
        assigned_subjects = Subject.objects.filter(
            is_active=True,
            classassignment__isnull=False
        ).distinct().count()
        context['assigned_subjects'] = assigned_subjects
        
        context['total_classes'] = len(CLASS_LEVEL_CHOICES)
        
        # Get unique academic years for filter suggestions
        academic_years = ClassAssignment.objects.values_list(
            'academic_year', 
            flat=True
        ).distinct().order_by('-academic_year')
        context['academic_years'] = academic_years
        
        # Add current academic year
        current_year = datetime.datetime.now().year
        context['current_year'] = f"{current_year}/{current_year + 1}"
        
        # Add role information for template
        context['is_admin'] = is_admin(self.request.user)
        context['is_teacher'] = is_teacher(self.request.user)
        
        print(f"\nContext data being sent to template:")
        print(f"  total_subjects: {total_subjects}")
        print(f"  assigned_subjects: {assigned_subjects}")
        print(f"  subjects list length: {subjects_with_counts.count()}")
        print(f"  is_admin: {context['is_admin']}")
        print(f"  is_teacher: {context['is_teacher']}")
        print("=" * 50)
        
        return context


class ClassAssignmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ClassAssignment
    form_class = ClassAssignmentForm
    template_name = 'core/academics/classes/class_assignment_form.html'
    success_url = reverse_lazy('class_assignment_list')
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        
        # If teacher is creating, pre-fill the teacher field
        if is_teacher(self.request.user) and hasattr(self.request.user, 'teacher'):
            kwargs['initial'] = {'teacher': self.request.user.teacher}
        
        return kwargs
    
    def form_valid(self, form):
        # Check if there's a qualification warning
        if hasattr(form, 'qualification_warning') and form.qualification_warning:
            # Add a warning message but still allow the assignment
            messages.warning(
                self.request,
                f"Teacher {form.unqualified_teacher.get_full_name()} was assigned to teach {form.unqualified_subject.name} "
                f"even though they are not currently qualified for this subject. "
                f"Consider adding this subject to their qualifications."
            )
        else:
            messages.success(self.request, 'Class assignment created successfully!')
        
        # Always set the teacher - either from the form or from the current user
        if not form.instance.teacher:
            if is_teacher(self.request.user):
                form.instance.teacher = self.request.user.teacher
            else:
                # For admins, you might want to handle this differently
                # Maybe add the teacher field to the form for admins
                form.add_error(None, "Teacher is required")
                return self.form_invalid(form)
        
        response = super().form_valid(form)
        
        # Add created parameter to redirect URL
        redirect_url = reverse_lazy('class_assignment_list') + '?created=true'
        return redirect(redirect_url)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_create'] = True
        context['is_admin'] = is_admin(self.request.user)
        context['is_teacher'] = is_teacher(self.request.user)
        
        # DEBUG: Add subject list for debugging
        context['debug_subjects'] = Subject.objects.filter(is_active=True).values('id', 'name', 'code')
        return context


class ClassAssignmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ClassAssignment
    form_class = ClassAssignmentForm
    template_name = 'core/academics/classes/class_assignment_form.html'
    success_url = reverse_lazy('class_assignment_list')
    
    def test_func(self):
        if is_admin(self.request.user):
            return True
        if is_teacher(self.request.user):
            return self.get_object().teacher == self.request.user.teacher
        return False
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        # Check if there's a qualification warning
        if hasattr(form, 'qualification_warning') and form.qualification_warning:
            messages.warning(
                self.request,
                f"Teacher {form.unqualified_teacher.get_full_name()} was assigned to teach {form.unqualified_subject.name} "
                f"even though they are not currently qualified for this subject."
            )
        else:
            messages.success(self.request, 'Class assignment updated successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True
        context['is_admin'] = is_admin(self.request.user)
        context['is_teacher'] = is_teacher(self.request.user)
        return context

class ClassAssignmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ClassAssignment
    form_class = ClassAssignmentForm
    template_name = 'core/academics/classes/class_assignment_form.html'
    success_url = reverse_lazy('class_assignment_list')
    
    def test_func(self):
        if is_admin(self.request.user):
            return True
        if is_teacher(self.request.user):
            return self.get_object().teacher == self.request.user.teacher
        return False
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        # Check if there's a qualification warning
        if hasattr(form, 'qualification_warning') and form.qualification_warning:
            messages.warning(
                self.request,
                f"Teacher {form.unqualified_teacher.get_full_name()} was assigned to teach {form.unqualified_subject.name} "
                f"even though they are not currently qualified for this subject."
            )
        else:
            messages.success(self.request, 'Class assignment updated successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True
        context['is_admin'] = is_admin(self.request.user)
        context['is_teacher'] = is_teacher(self.request.user)
        return context


class ClassAssignmentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ClassAssignment
    template_name = 'core/academics/classes/class_assignment_confirm_delete.html'
    success_url = reverse_lazy('class_assignment_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Class assignment deleted successfully')
        return super().delete(request, *args, **kwargs)


# API View for getting students in a class assignment
def get_assignment_students(request, assignment_id):
    """API endpoint to get students for a class assignment"""
    try:
        print(f"Debug: Getting students for assignment ID: {assignment_id}")
        
        # Check permission
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        
        assignment = ClassAssignment.objects.get(id=assignment_id)
        
        # Check if user has permission to view these students
        if not (is_admin(request.user) or 
                (is_teacher(request.user) and assignment.teacher == request.user.teacher)):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        # Debug: Print assignment details
        print(f"Debug: Found assignment - Class Level: {assignment.class_level}")
        print(f"Debug: Subject: {assignment.subject.name}")
        
        # Get students in this class level
        students = Student.objects.filter(
            class_level=assignment.class_level,
            is_active=True
        ).select_related('user').order_by('last_name', 'first_name')
        
        # Debug: Print student count
        print(f"Debug: Found {students.count()} students in class level {assignment.class_level}")
        
        student_list = []
        for student in students:
            student_list.append({
                'id': student.id,
                'student_id': student.student_id,
                'full_name': f"{student.first_name} {student.last_name}",
                'first_name': student.first_name,
                'last_name': student.last_name,
                'gender': 'Male' if student.gender == 'M' else 'Female',
                'class_level': student.get_class_level_display(),
                'is_active': student.is_active
            })
        
        return JsonResponse({
            'success': True,
            'class_display': f"{assignment.get_class_level_display()} - {assignment.subject.name}",
            'students': student_list,
            'count': len(student_list)
        })
        
    except ClassAssignment.DoesNotExist:
        print(f"Debug: Assignment with ID {assignment_id} not found")
        return JsonResponse({
            'success': False,
            'error': f'Class assignment with ID {assignment_id} not found'
        }, status=404)
    except Exception as e:
        print(f"Debug: Error getting students: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Add debug API endpoint
def debug_database_stats(request):
    """Debug endpoint to check database state"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    
    try:
        # Get all subjects
        subjects = Subject.objects.all().values('id', 'name', 'code', 'is_active')
        
        # Get subjects with assignments
        subjects_with_assignments = Subject.objects.filter(
            classassignment__isnull=False
        ).distinct().values_list('id', flat=True)
        
        # Count assignments per subject
        subject_assignment_counts = []
        for subject in Subject.objects.all():
            count = ClassAssignment.objects.filter(subject=subject).count()
            subject_assignment_counts.append({
                'subject_id': subject.id,
                'subject_name': subject.name,
                'assignment_count': count
            })
        
        return JsonResponse({
            'success': True,
            'total_subjects': Subject.objects.count(),
            'active_subjects': Subject.objects.filter(is_active=True).count(),
            'subjects_with_assignments': len(subjects_with_assignments),
            'all_subjects': list(subjects),
            'subject_assignment_counts': subject_assignment_counts,
            'total_assignments': ClassAssignment.objects.count(),
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# Teacher Qualification Update View
class TeacherQualificationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Teacher
    fields = ['subjects']
    template_name = 'core/academics/classes/teacher_qualification_form.html'
    success_url = reverse_lazy('teacher_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.get_object()
        
        # Get all active subjects
        all_subjects = Subject.objects.filter(is_active=True).order_by('name')
        
        # Calculate remaining subjects that teacher can add
        teacher_subjects = set(teacher.subjects.all())
        all_subjects_set = set(all_subjects)
        remaining_count = len(all_subjects_set - teacher_subjects)
        
        context.update({
            'all_subjects': all_subjects,
            'remaining_count': remaining_count,
        })
        
        return context
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            f'Teacher {self.object.get_full_name()}\'s qualifications updated successfully!'
        )
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(
            self.request, 
            'Please correct the errors below.'
        )
        return super().form_invalid(form)


def get_teacher_qualifications(request, teacher_id):
    """API endpoint to get teacher qualifications"""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        
        if not is_admin(request.user):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        teacher = Teacher.objects.get(id=teacher_id)
        subjects = teacher.subjects.filter(is_active=True).values('id', 'name', 'code')
        
        return JsonResponse({
            'success': True,
            'teacher': {
                'id': teacher.id,
                'employee_id': teacher.employee_id,
                'full_name': teacher.get_full_name(),
                'is_active': teacher.is_active,
            },
            'subjects': list(subjects),
            'count': subjects.count()
        })
        
    except Teacher.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Teacher not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Additional helper view for assignment statistics
def assignment_statistics(request):
    """API endpoint for assignment statistics"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    
    if not is_admin(request.user) and not is_teacher(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    try:
        # Basic statistics
        total_assignments = ClassAssignment.objects.count()
        active_assignments = ClassAssignment.objects.filter(is_active=True).count()
        
        # Subject statistics
        subject_stats = []
        subjects = Subject.objects.filter(is_active=True).annotate(
            assignment_count=Count('classassignment'),
            active_assignment_count=Count('classassignment', filter=Q(classassignment__is_active=True))
        ).order_by('name')
        
        for subject in subjects:
            subject_stats.append({
                'name': subject.name,
                'code': subject.code,
                'total_assignments': subject.assignment_count,
                'active_assignments': subject.active_assignment_count
            })
        
        # Teacher statistics
        teacher_stats = []
        teachers = Teacher.objects.filter(is_active=True).annotate(
            assignment_count=Count('classassignment'),
            active_assignment_count=Count('classassignment', filter=Q(classassignment__is_active=True))
        ).order_by('user__last_name', 'user__first_name')
        
        for teacher in teachers:
            teacher_stats.append({
                'name': teacher.get_full_name(),
                'employee_id': teacher.employee_id,
                'total_assignments': teacher.assignment_count,
                'active_assignments': teacher.active_assignment_count
            })
        
        # Class level statistics
        class_stats = []
        for class_level, display_name in CLASS_LEVEL_CHOICES:
            count = ClassAssignment.objects.filter(
                class_level=class_level,
                is_active=True
            ).count()
            
            if count > 0 or is_admin(request.user):
                class_stats.append({
                    'class_level': class_level,
                    'display_name': display_name,
                    'assignment_count': count
                })
        
        return JsonResponse({
            'success': True,
            'total_assignments': total_assignments,
            'active_assignments': active_assignments,
            'subject_statistics': subject_stats,
            'teacher_statistics': teacher_stats,
            'class_statistics': class_stats,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Quick assignment creation view for admins
class QuickClassAssignmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Quick assignment creation for multiple classes at once"""
    model = ClassAssignment
    form_class = ClassAssignmentForm
    template_name = 'core/academics/classes/quick_assignment_form.html'
    success_url = reverse_lazy('class_assignment_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['is_quick_create'] = True
        return kwargs
    
    def form_valid(self, form):
        # Handle multiple class levels
        class_levels = self.request.POST.getlist('class_levels')
        
        if not class_levels:
            form.add_error(None, "Please select at least one class level")
            return self.form_invalid(form)
        
        created_assignments = []
        failed_assignments = []
        
        for class_level in class_levels:
            # Check if assignment already exists
            existing = ClassAssignment.objects.filter(
                class_level=class_level,
                subject=form.instance.subject,
                academic_year=form.instance.academic_year,
                teacher=form.instance.teacher
            ).exists()
            
            if existing:
                failed_assignments.append({
                    'class_level': class_level,
                    'reason': 'Assignment already exists'
                })
                continue
            
            # Create new assignment
            assignment = ClassAssignment(
                class_level=class_level,
                subject=form.instance.subject,
                teacher=form.instance.teacher,
                academic_year=form.instance.academic_year,
                is_active=form.instance.is_active
            )
            
            try:
                assignment.full_clean()
                assignment.save()
                created_assignments.append(assignment)
            except Exception as e:
                failed_assignments.append({
                    'class_level': class_level,
                    'reason': str(e)
                })
        
        # Show success/error messages
        if created_assignments:
            messages.success(
                self.request, 
                f'Successfully created {len(created_assignments)} assignments.'
            )
        
        if failed_assignments:
            for failed in failed_assignments:
                messages.warning(
                    self.request,
                    f"Failed to create assignment for {failed['class_level']}: {failed['reason']}"
                )
        
        if not created_assignments and failed_assignments:
            # All failed, redirect back to form
            return self.form_invalid(form)
        
        return redirect(self.success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['class_levels'] = CLASS_LEVEL_CHOICES
        context['is_quick_create'] = True
        return context


# Bulk delete assignments
def bulk_delete_assignments(request):
    """Bulk delete assignments (admin only)"""
    if not request.user.is_authenticated or not is_admin(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        assignment_ids = request.POST.getlist('assignment_ids[]')
        
        if not assignment_ids:
            return JsonResponse({'success': False, 'error': 'No assignments selected'}, status=400)
        
        # Convert to integers
        assignment_ids = [int(id) for id in assignment_ids if id.isdigit()]
        
        # Delete assignments
        deleted_count, _ = ClassAssignment.objects.filter(id__in=assignment_ids).delete()
        
        # Log the action
        AuditLog.log_action(
            user=request.user,
            action='DELETE',
            model_name='ClassAssignment',
            object_id=', '.join(str(id) for id in assignment_ids),
            details={'count': deleted_count, 'ids': assignment_ids}
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted {deleted_count} assignments',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Toggle assignment status
def toggle_assignment_status(request, assignment_id):
    """Toggle assignment active/inactive status"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    
    try:
        assignment = ClassAssignment.objects.get(id=assignment_id)
        
        # Check permissions
        if not (is_admin(request.user) or 
                (is_teacher(request.user) and assignment.teacher == request.user.teacher)):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        # Toggle status
        assignment.is_active = not assignment.is_active
        assignment.save()
        
        status_text = "activated" if assignment.is_active else "deactivated"
        
        # Log the action
        AuditLog.log_action(
            user=request.user,
            action='UPDATE',
            model_name='ClassAssignment',
            object_id=assignment_id,
            details={'field': 'is_active', 'new_value': assignment.is_active}
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Assignment {status_text} successfully',
            'is_active': assignment.is_active,
            'status_display': 'Active' if assignment.is_active else 'Inactive'
        })
        
    except ClassAssignment.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Assignment not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Import/Export views for assignments
class ExportAssignmentsView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Export assignments to CSV/Excel"""
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get(self, request, *args, **kwargs):
        format_type = request.GET.get('format', 'csv')
        response = HttpResponse(content_type='text/csv' if format_type == 'csv' else 'application/vnd.ms-excel')
        
        if format_type == 'csv':
            response['Content-Disposition'] = 'attachment; filename="class_assignments.csv"'
            writer = csv.writer(response)
            writer.writerow(['Class Level', 'Subject', 'Teacher', 'Academic Year', 'Status', 'Created At'])
        else:
            response['Content-Disposition'] = 'attachment; filename="class_assignments.xlsx"'
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = 'Class Assignments'
            worksheet.append(['Class Level', 'Subject', 'Teacher', 'Academic Year', 'Status', 'Created At'])
        
        # Get assignments based on user role
        if is_teacher(request.user):
            assignments = ClassAssignment.objects.filter(teacher=request.user.teacher)
        else:
            assignments = ClassAssignment.objects.all()
        
        for assignment in assignments:
            row = [
                assignment.get_class_level_display(),
                assignment.subject.name,
                assignment.teacher.get_full_name(),
                assignment.academic_year,
                'Active' if assignment.is_active else 'Inactive',
                assignment.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            if format_type == 'csv':
                writer.writerow(row)
            else:
                worksheet.append(row)
        
        if format_type == 'excel':
            workbook.save(response)
        
        return response