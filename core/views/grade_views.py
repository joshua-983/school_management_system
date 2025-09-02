from django.views.generic import TemplateView,  ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.db.models import Avg, Max, Min, Count, Sum, Q
from django.core.files.base import ContentFile
from openpyxl import load_workbook
from io import BytesIO, StringIO
import csv
from decimal import Decimal
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .base_views import *
from ..models import Grade, Assignment, StudentAssignment, ReportCard, Student, Subject, ClassAssignment
from ..forms import GradeForm, GradeEntryForm, ReportCardForm, ReportCardFilterForm

class GradeListView(LoginRequiredMixin, ListView):
    model = Grade
    template_name = 'core/academics/grades/grade_list.html'
    context_object_name = 'grades'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'student', 'subject', 'class_assignment'
        )
        
        # Apply filters
        student_id = self.request.GET.get('student')
        subject_id = self.request.GET.get('subject')
        class_level = self.request.GET.get('class_level')
        academic_year = self.request.GET.get('academic_year')
        term = self.request.GET.get('term')
        
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if class_level:
            queryset = queryset.filter(class_assignment__class_level=class_level)
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        if term:
            queryset = queryset.filter(term=term)
        
        # Role-based filtering
        if is_teacher(self.request.user):
            class_assignments = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            queryset = queryset.filter(
                class_assignment__class_level__in=class_assignments
            )
        elif is_student(self.request.user):
            queryset = queryset.filter(student=self.request.user.student)
        
        return queryset.order_by('-academic_year', '-term', 'student__last_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['students'] = Student.objects.all().order_by('last_name', 'first_name')
        context['subjects'] = Subject.objects.all().order_by('name')
        context['class_levels'] = Student.CLASS_LEVEL_CHOICES
        
        # Add statistics
        queryset = self.get_queryset()
        context['total_grades'] = queryset.count()
        context['total_students'] = Student.objects.count()
        context['total_subjects'] = Subject.objects.count()
        
        # Calculate average score
        if context['total_grades'] > 0:
            total_score = sum(float(grade.total_score or 0) for grade in queryset if grade.total_score is not None)
            context['average_grade'] = total_score / context['total_grades']
        else:
            context['average_grade'] = 0
        
        # Current filter values
        context['current_filters'] = {
            'student': self.request.GET.get('student', ''),
            'subject': self.request.GET.get('subject', ''),
            'class_level': self.request.GET.get('class_level', ''),
            'academic_year': self.request.GET.get('academic_year', ''),
            'term': self.request.GET.get('term', ''),
        }
        
        return context
    
def grade_delete(request, pk):
    grade = get_object_or_404(Grade, pk=pk)
    if request.method == 'POST':
        grade.delete()
        messages.success(request, 'Grade record deleted successfully.')
        return redirect('grade_list')
    
    # For GET requests, you might want to show a confirmation page
    # If you want a confirmation page, create it and render it here
    # return render(request, 'core/grades/confirm_delete.html', {'grade': grade})
    
    # Or directly delete on GET (not recommended for production)
    grade.delete()
    messages.success(request, 'Grade record deleted successfully.')
    return redirect('grade_list')
class GradeUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Grade
    form_class = GradeForm
    template_name = 'core/academics/grades/grade_form.html'
    
    def get_object(self, queryset=None):
        """Get the grade object with proper error handling"""
        try:
            return super().get_object(queryset)
        except Http404:
            messages.error(self.request, "The requested grade record does not exist")
            raise

    def test_func(self):
        """Check permissions for accessing this view"""
        try:
            grade = self.get_object()
            
            if is_admin(self.request.user):
                return True
                
            if is_teacher(self.request.user):
                # Check if teacher teaches this class and subject
                return ClassAssignment.objects.filter(
                    Q(class_level=grade.class_assignment.class_level) &
                    Q(teacher=self.request.user.teacher) &
                    Q(subject=grade.subject)
                ).exists()
                
            return False
            
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}", exc_info=True)
            return False

    @transaction.atomic
    def form_valid(self, form):
        """Handle successful form submission with transaction safety"""
        try:
            # Debug before save
            logger.info(f"Updating grade for student {self.object.student}")
            
            # Get original values for comparison
            original_scores = {
                'homework': self.object.homework_score,
                'classwork': self.object.classwork_score,
                'test': self.object.test_score,
                'exam': self.object.exam_score
            }
            
            # Save the form
            response = super().form_valid(form)
            
            # Check for score changes
            score_changed = any(
                str(original_scores[score_type]) != str(form.cleaned_data[f"{score_type}_score"])
                for score_type in ['homework', 'classwork', 'test', 'exam']
            )
            
            if score_changed:
                self.send_grade_notification()
                messages.success(self.request, 'Grade updated successfully with notifications sent')
            else:
                messages.info(self.request, 'Grade saved (no changes to scores)')
                
            return response
            
        except Exception as e:
            logger.error(f"Error saving grade: {str(e)}", exc_info=True)
            messages.error(self.request, 'Error saving grade. Please try again.')
            return self.form_invalid(form)

    def send_grade_notification(self):
        """Send WebSocket notifications about grade update"""
        try:
            student = self.object.student
            subject = self.object.subject
            
            notification_data = {
                'type': 'send_notification',
                'notification_type': 'GRADE_UPDATE',
                'title': 'Grade Updated',
                'message': f'Your {subject.name} grade has been updated',
                'related_object_id': self.object.id,
                'timestamp': str(timezone.now()),
                'icon': 'bi-journal-check',
                'color': 'info'
            }
            
            # Notify student
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notifications_{student.user.id}',
                notification_data
            )
            
            # Notify admin if teacher made the change
            if is_teacher(self.request.user):
                self.notify_admin_about_update()
                
        except Exception as e:
            logger.error(f"Notification failed: {str(e)}")

    def notify_admin_about_update(self):
        """Notify admins about grade changes"""
        try:
            admins = User.objects.filter(is_superuser=True)
            for admin in admins:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{admin.id}',
                    {
                        'type': 'send_notification',
                        'notification_type': 'GRADE_MODIFIED',
                        'title': 'Grade Modified',
                        'message': f'{self.request.user} updated grade for {self.object.student}',
                        'related_object_id': self.object.id,
                        'timestamp': str(timezone.now())
                    }
                )
        except Exception as e:
            logger.error(f"Admin notification failed: {str(e)}")

    def get_success_url(self):
        return reverse_lazy('grade_list')

    def get_context_data(self, **kwargs):
        """Add additional context for the template"""
        context = super().get_context_data(**kwargs)
        context['student'] = self.object.student
        context['subject'] = self.object.subject
        context['is_teacher'] = is_teacher(self.request.user)
        return context

class BulkGradeUploadView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'core/academics/grades/bulk_grade_upload.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_assignments_queryset(self):
        if is_admin(self.request.user):
            return Assignment.objects.all().select_related('class_assignment', 'subject')
        elif is_teacher(self.request.user):
            try:
                teacher = self.request.user.teacher
                return Assignment.objects.filter(
                    class_assignment__teacher=teacher
                ).select_related('class_assignment', 'subject')
            except AttributeError:
                return Assignment.objects.none()
        return Assignment.objects.none()
    
    def get(self, request):
        form = BulkGradeUploadForm(request=request)
        return render(request, self.template_name, {'form': form})
    
    def process_grade_row(self, row, assignment, term):
        """Process a single row of grade data"""
        # Normalize column names
        row = {k.lower().strip(): v for k, v in row.items()}
        
        student_id = row.get('student_id') or row.get('student id')
        if not student_id:
            raise ValueError("Missing student ID")
        
        try:
            student = Student.objects.get(student_id=student_id)
        except Student.DoesNotExist:
            raise ValueError(f"Student with ID {student_id} not found")
        
        try:
            score = float(row.get('score', 0))
            if score < 0 or score > assignment.max_score:
                raise ValueError(f"Score {score} is outside valid range (0-{assignment.max_score})")
        except (ValueError, TypeError):
            raise ValueError("Invalid score format - must be a number")
        
        # Convert academic year format from YYYY-YYYY to YYYY/YYYY
        academic_year = assignment.class_assignment.academic_year
        if '-' in academic_year:
            academic_year = academic_year.replace('-', '/')
        
        # Update or create Grade record
        grade, created = Grade.objects.update_or_create(
            student=student,
            subject=assignment.subject,
            class_assignment=assignment.class_assignment,
            academic_year=academic_year,  # Use converted format
            term=term,
            defaults={
                'homework_score': 0,
                'classwork_score': 0,
                'test_score': 0,
                'exam_score': 0,
            }
        )
        
        # Update the appropriate score based on assignment type
        score_field = f"{assignment.assignment_type.lower()}_score"
        if hasattr(grade, score_field):
            setattr(grade, score_field, score)
            grade.save()
        else:
            raise ValueError(f"Invalid assignment type: {assignment.assignment_type}")
        
        # Update student assignment status
        StudentAssignment.objects.update_or_create(
            student=student,
            assignment=assignment,
            defaults={
                'score': score,
                'status': 'GRADED',
                'graded_at': timezone.now()
            }
        )
    
    def post(self, request):
        form = BulkGradeUploadForm(request.POST, request.FILES, request=request)
        
        if form.is_valid():
            assignment = form.cleaned_data['assignment']
            term = form.cleaned_data['term']
            file = form.cleaned_data['file']
            ext = file.name.split('.')[-1].lower()
            
            try:
                success_count = 0
                error_messages = []
                
                if ext == 'csv':
                    decoded_file = file.read().decode('utf-8').splitlines()
                    reader = csv.DictReader(decoded_file)
                    for row_num, row in enumerate(reader, 2):
                        try:
                            self.process_grade_row(row, assignment, term)
                            success_count += 1
                        except Exception as e:
                            error_messages.append(f"Row {row_num}: {str(e)}")
                else:
                    wb = load_workbook(filename=BytesIO(file.read()))
                    sheet = wb.active
                    headers = [cell.value for cell in sheet[1]]
                    for row_num, row in enumerate(sheet.iter_rows(min_row=2), 2):
                        try:
                            row_data = dict(zip(headers, [cell.value for cell in row]))
                            self.process_grade_row(row_data, assignment, term)
                            success_count += 1
                        except Exception as e:
                            error_messages.append(f"Row {row_num}: {str(e)}")
                
                if success_count > 0:
                    messages.success(request, f'Successfully processed {success_count} grades')
                if error_messages:
                    messages.warning(request, 'Some grades could not be processed:')
                    for msg in error_messages[:5]:
                        messages.warning(request, msg)
                    if len(error_messages) > 5:
                        messages.warning(request, f'...and {len(error_messages)-5} more errors')
                
                return redirect('grade_list')
                
            except Exception as e:
                messages.error(request, f'Error processing file: {str(e)}')
                logger.error(f"Bulk grade upload failed: {str(e)}", exc_info=True)
        
        return render(request, self.template_name, {'form': form})

class GradeUploadTemplateView(View):
    def get(self, request):
        # Create a CSV file in memory
        buffer = StringIO()
        writer = csv.writer(buffer)
        
        # Write header row
        writer.writerow(['student_id', 'score'])
        
        # Create the response
        response = HttpResponse(buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="grade_upload_template.csv"'
        return response
    

#GRADE ENTRIES
class GradeEntryView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Grade
    form_class = GradeEntryForm
    template_name = 'core/academics/grades/grade_entry.html'
    success_url = reverse_lazy('grade_list')

    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # Pass initial data if student is selected in GET parameters
        if self.request.method == 'GET':
            initial = kwargs.get('initial', {})
            student_id = self.request.GET.get('student')
            if student_id:
                try:
                    initial['student'] = Student.objects.get(pk=student_id)
                except (Student.DoesNotExist, ValueError):
                    pass
            kwargs['initial'] = initial
        
        return kwargs

    def form_valid(self, form):
        # Set the class_assignment automatically based on student's class and subject
        student = form.cleaned_data['student']
        subject = form.cleaned_data['subject']
        assignment = form.cleaned_data['assignment']
        
        try:
            class_assignment = ClassAssignment.objects.get(
                class_level=student.class_level,
                subject=subject
            )
            form.instance.class_assignment = class_assignment
        except ClassAssignment.DoesNotExist:
            form.add_error(None, "No class assignment exists for this student's class and subject")
            return self.form_invalid(form)
        
        # Set recorded by
        form.instance.recorded_by = self.request.user
        
        # Auto-calculate grade if not provided
        if not form.instance.grade and form.instance.score is not None:
            form.instance.grade = self.calculate_grade(form.instance.score)
        
        messages.success(self.request, 'Grade successfully recorded!')
        return super().form_valid(form)

    def calculate_grade(self, score):
        """Calculate letter grade based on score"""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add student's previous grades if student is selected
        student_id = self.request.GET.get('student')
        if student_id:
            try:
                student = Student.objects.get(pk=student_id)
                context['previous_grades'] = Grade.objects.filter(
                    student=student
                ).select_related('subject', 'assignment').order_by('-academic_year', '-term')[:10]
            except (Student.DoesNotExist, ValueError):
                context['previous_grades'] = Grade.objects.none()
        else:
            context['previous_grades'] = Grade.objects.none()
                
        return context

    def get_success_url(self):
        messages.success(self.request, 'Grade recorded successfully!')
        return super().get_success_url()
#grade reports
class GradeReportView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/academics/grades/grade_report.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        subject_id = self.request.GET.get('subject')
        class_level = self.request.GET.get('class_level')
        academic_year = self.request.GET.get('academic_year')
        term = self.request.GET.get('term')
        
        # Get available filter options
        if is_teacher(self.request.user):
            context['subjects'] = self.request.user.teacher.subjects.all()
            context['class_levels'] = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True).distinct()
        else:
            context['subjects'] = Subject.objects.all()
            context['class_levels'] = Student.CLASS_LEVEL_CHOICES
        
        # Apply filters if provided
        if subject_id and class_level and academic_year and term:
            subject = get_object_or_404(Subject, pk=subject_id)
            
            # Get grades
            grades = Grade.objects.filter(
                subject=subject,
                student__class_level=class_level,
                academic_year=academic_year,
                term=term
            ).select_related('student').order_by('student__last_name')
            
            # Calculate statistics
            class_average = grades.aggregate(Avg('total_score'))['total_score__avg']
            grade_distribution = grades.values('ges_grade').annotate(
                count=Count('id'),
                percentage=ExpressionWrapper(
                    Count('id') * 100.0 / grades.count(),
                    output_field=FloatField()
                )
            ).order_by('ges_grade')
            
            passing_rate = grades.filter(is_passing=True).count() / grades.count() * 100 if grades.count() > 0 else 0
            
            context.update({
                'selected_subject': subject,
                'selected_class_level': class_level,
                'selected_academic_year': academic_year,
                'selected_term': term,
                'grades': grades,
                'class_average': class_average,
                'grade_distribution': grade_distribution,
                'passing_rate': passing_rate,
                'show_results': True
            })
        
        return context

#best students view
class BestStudentsView(LoginRequiredMixin, TemplateView):
    template_name = 'core/academics/grades/best_students.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        top_students = Student.objects.annotate(
            avg_grade=Avg('grades__score')
        ).order_by('-avg_grade')[:10]
        
        # Debug output
        print(f"Found {len(top_students)} top students")
        for student in top_students:
            print(f"Student: {student.full_name}, Avg Grade: {student.avg_grade}")
        
        context.update({
            'top_students': top_students,
            'current_year': timezone.now().year
        })
        return context
