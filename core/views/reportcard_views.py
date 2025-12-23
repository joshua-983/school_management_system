"""
Report Card Views - Complete implementation with all fixes
"""
import re
import logging
from datetime import datetime
from django.db.models import Avg, Count, Q
from django.views.generic import TemplateView, CreateView, View, FormView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from django.http import HttpResponse, Http404, JsonResponse

# ReportLab for PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors

# Import utils from core.utils
from core.utils import (
    is_admin, is_teacher, is_student, is_parent,
    calculate_letter_grade, get_current_academic_year,
    get_grade_color, get_performance_level, format_date,
    calculate_total_score, validate_academic_year,
    check_report_card_permission, can_edit_grades,
    get_student_position_in_class, get_attendance_summary,
    get_class_level_display
)

# Import models
from core.models.report_card import ReportCard
from core.models.grades import Grade
from core.models import (
    Student, Subject, StudentAttendance, AcademicTerm,
    ClassAssignment, SchoolConfiguration
)

# Import forms
from core.forms import ReportCardGenerationForm, ReportCardFilterForm

logger = logging.getLogger(__name__)


class ReportCardDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard view for managing report cards
    """
    template_name = 'core/academics/report_cards/report_card_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Debug logging
        logger.debug(f"Dashboard - User: {self.request.user}")
        logger.debug(f"Dashboard - Is teacher: {is_teacher(self.request.user)}")
        logger.debug(f"Dashboard - Is admin: {is_admin(self.request.user)}")
        logger.debug(f"Dashboard - Is student: {is_student(self.request.user)}")
        
        # Get report cards based on user role
        if is_student(self.request.user):
            student = self.request.user.student
            report_cards = ReportCard.objects.filter(
                student=student
            ).select_related('student').order_by('-academic_year', '-term')
            
            # Student can only see published report cards
            report_cards = report_cards.filter(is_published=True)
        
        elif is_teacher(self.request.user):
            try:
                # Get classes this teacher teaches
                teacher_classes = ClassAssignment.objects.filter(
                    teacher=self.request.user.teacher
                ).values_list('class_level', flat=True).distinct()
                
                logger.debug(f"Teacher classes: {list(teacher_classes)}")
                
                # Get report cards for students in those classes
                report_cards = ReportCard.objects.filter(
                    student__class_level__in=teacher_classes
                ).select_related('student').order_by('-academic_year', '-term')
                
                # Add teacher's students for quick view modal
                context['teacher_students'] = Student.objects.filter(
                    class_level__in=teacher_classes,
                    is_active=True
                ).order_by('class_level', 'last_name', 'first_name')
                
                logger.debug(f"Teacher students count: {context['teacher_students'].count()}")
                
            except Exception as e:
                logger.error(f"Error getting teacher data: {e}")
                report_cards = ReportCard.objects.none()
                context['teacher_students'] = Student.objects.none()
        
        else:
            # Admin or other users see all report cards
            report_cards = ReportCard.objects.all().select_related('student').order_by('-academic_year', '-term')
            
            # Add all students for quick view modal
            context['all_students'] = Student.objects.filter(
                is_active=True
            ).order_by('class_level', 'last_name', 'first_name')
            
            logger.debug(f"All students count: {context['all_students'].count()}")
        
        # Apply filters from GET parameters
        academic_year = self.request.GET.get('academic_year')
        term = self.request.GET.get('term')
        class_level = self.request.GET.get('class_level')
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        grade_range = self.request.GET.get('grade_range')
        sort_by = self.request.GET.get('sort_by')
        
        logger.debug(f"Filters - Year: {academic_year}, Term: {term}, Class: {class_level}, Status: {status}")
        
        if academic_year:
            report_cards = report_cards.filter(academic_year=academic_year)
        if term:
            report_cards = report_cards.filter(term=term)
        if class_level:
            report_cards = report_cards.filter(student__class_level=class_level)
        if status == 'published':
            report_cards = report_cards.filter(is_published=True)
        elif status == 'draft':
            report_cards = report_cards.filter(is_published=False)
        if search:
            report_cards = report_cards.filter(
                Q(student__first_name__icontains=search) |
                Q(student__last_name__icontains=search) |
                Q(student__student_id__icontains=search)
            )
        if grade_range:
            if grade_range == 'A':
                report_cards = report_cards.filter(overall_grade__in=['A+', 'A'])
            elif grade_range == 'B':
                report_cards = report_cards.filter(overall_grade__in=['B+', 'B'])
            elif grade_range == 'C':
                report_cards = report_cards.filter(overall_grade__in=['C+', 'C'])
            elif grade_range == 'D':
                report_cards = report_cards.filter(overall_grade__in=['D+', 'D'])
            elif grade_range == 'E':
                report_cards = report_cards.filter(overall_grade='E')
        
        # Apply sorting
        if sort_by == 'score_asc':
            report_cards = report_cards.order_by('average_score')
        elif sort_by == 'score_desc':
            report_cards = report_cards.order_by('-average_score')
        elif sort_by == 'name_asc':
            report_cards = report_cards.order_by('student__last_name', 'student__first_name')
        elif sort_by == 'name_desc':
            report_cards = report_cards.order_by('-student__last_name', '-student__first_name')
        elif sort_by == 'recent':
            report_cards = report_cards.order_by('-updated_at')
        else:
            report_cards = report_cards.order_by('-academic_year', '-term', 'student__last_name')
        
        # Calculate statistics
        total_count = report_cards.count()
        published_count = report_cards.filter(is_published=True).count()
        draft_count = report_cards.filter(is_published=False).count()
        
        # Calculate average score (handle None values)
        valid_scores = report_cards.exclude(average_score__isnull=True)
        avg_score = valid_scores.aggregate(avg=Avg('average_score'))['avg'] or 0
        
        # Calculate needs attention count (grades E, D, D+, C)
        needs_attention_count = report_cards.filter(
            overall_grade__in=['E', 'D', 'D+', 'C']
        ).count()
        
        # Calculate current term count
        current_year = timezone.now().year
        current_academic_year = f"{current_year}/{current_year + 1}"
        current_term_count = report_cards.filter(
            academic_year=current_academic_year,
            term=2  # Default to term 2
        ).count()
        
        logger.debug(f"Report cards count: {total_count}")
        logger.debug(f"Avg score: {avg_score}")
        
        # Ensure student lists are always available for the modal
        if 'teacher_students' not in context and 'all_students' not in context:
            # Fallback: provide at least some students
            if is_teacher(self.request.user):
                context['teacher_students'] = Student.objects.filter(is_active=True)[:10]
            else:
                context['all_students'] = Student.objects.filter(is_active=True)[:10]
        
        # Pagination
        paginator = Paginator(report_cards, 20)  # Show 20 report cards per page
        page = self.request.GET.get('page')
        try:
            report_cards_page = paginator.page(page)
        except PageNotAnInteger:
            report_cards_page = paginator.page(1)
        except EmptyPage:
            report_cards_page = paginator.page(paginator.num_pages)
        
        # Add context data
        context.update({
            'report_cards': report_cards_page,
            'total_count': total_count,
            'published_count': published_count,
            'draft_count': draft_count,
            'avg_score': round(avg_score, 1),
            'needs_attention_count': needs_attention_count,
            'current_term_count': current_term_count,
            'is_teacher': is_teacher(self.request.user),
            'is_admin': is_admin(self.request.user),
            'is_student': is_student(self.request.user),
            'is_parent': is_parent(self.request.user),
            'current_academic_year': get_current_academic_year(),
        })
        
        return context


class QuickViewReportCardView(LoginRequiredMixin, View):
    """
    Quick view report card - redirects to the detailed view
    """
    
    def get(self, request):
        student_id = request.GET.get('student_id')
        academic_year = request.GET.get('academic_year')
        term = request.GET.get('term')
        view_type = request.GET.get('view_type', 'web')
        
        logger.debug(f"QuickView: student_id={student_id}, academic_year={academic_year}, term={term}, view_type={view_type}")
        
        if not all([student_id, academic_year, term]):
            messages.error(request, 'Please select student, academic year, and term')
            return redirect('report_card_dashboard')
        
        try:
            student = Student.objects.get(pk=student_id)
            
            # Check permissions using utils
            if not check_report_card_permission(request.user, student):
                raise PermissionDenied("You don't have permission to view this report card")
            
            # Try to find existing report card
            report_card = ReportCard.objects.filter(
                student=student,
                academic_year=academic_year,
                term=term
            ).first()
            
            logger.debug(f"QuickView: Found report_card = {report_card}")
            
            if view_type == 'pdf':
                # Handle PDF view
                if report_card:
                    return redirect('report_card_pdf_detail', student_id=student_id, report_card_id=report_card.id)
                else:
                    # Generate PDF directly from grades
                    return redirect(f'{reverse("report_card_pdf", kwargs={"student_id": student_id})}?academic_year={academic_year}&term={term}')
            else:
                # Handle Web view
                if report_card:
                    # Existing report card - go to detail view
                    return redirect('report_card_detail', student_id=student_id, report_card_id=report_card.id)
                else:
                    # No existing report card - go to preview mode
                    base_url = reverse('report_card', kwargs={'student_id': student_id})
                    params = f'academic_year={academic_year}&term={term}&preview=true'
                    redirect_url = f'{base_url}?{params}'
                    logger.debug(f"QuickView: No existing report card, redirecting to preview: {redirect_url}")
                    return redirect(redirect_url)
                
        except Student.DoesNotExist:
            messages.error(request, 'Student not found')
            return redirect('report_card_dashboard')
        except PermissionDenied as e:
            messages.error(request, str(e))
            return redirect('report_card_dashboard')
        except Exception as e:
            logger.error(f"Quick view error: {str(e)}", exc_info=True)
            messages.error(request, f'Error viewing report card: {str(e)}')
            return redirect('report_card_dashboard')


class CreateReportCardView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """
    View for creating new report cards
    """
    form_class = ReportCardGenerationForm
    template_name = 'core/academics/report_cards/create_report_card.html'
    success_url = reverse_lazy('report_card_dashboard')
    
    def test_func(self):
        """Only teachers and admins can create report cards"""
        return is_teacher(self.request.user) or is_admin(self.request.user)
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("You don't have permission to create report cards")
        return super().handle_no_permission()
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        try:
            student = form.cleaned_data['student']
            academic_year = form.cleaned_data['academic_year']
            term = form.cleaned_data['term']
            is_published = form.cleaned_data.get('is_published', False)
            
            # Check if report card already exists
            existing = ReportCard.objects.filter(
                student=student,
                academic_year=academic_year,
                term=term
            ).first()
            
            if existing:
                messages.warning(self.request, 
                    f'A report card already exists for {student.get_full_name()} '
                    f'for {academic_year} Term {term}')
                return redirect('report_card_detail', 
                    student_id=student.id, 
                    report_card_id=existing.id)
            
            # Create new report card
            report_card = ReportCard.objects.create(
                student=student,
                academic_year=academic_year,
                term=term,
                is_published=is_published,
                created_by=self.request.user
            )
            
            # Calculate grades from existing grades
            report_card.calculate_grades()
            report_card.save()
            
            messages.success(self.request, 
                f'Report card for {student.get_full_name()} created successfully!')
            
            # Redirect to the new report card
            return redirect('report_card_detail', 
                student_id=student.id, 
                report_card_id=report_card.id)
            
        except Exception as e:
            logger.error(f"Error creating report card: {str(e)}", exc_info=True)
            messages.error(self.request, f'Error creating report card: {str(e)}')
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Report Card'
        context['is_teacher'] = is_teacher(self.request.user)
        context['is_admin'] = is_admin(self.request.user)
        return context


class ReportCardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Enhanced ReportCardView with editable mode support
    """
    
    def test_func(self):
        student_id = self.kwargs.get('student_id')
        
        try:
            student_id = int(student_id)
        except (ValueError, TypeError):
            return False
        
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            return False
        
        # Use the utility function from core.utils
        return check_report_card_permission(self.request.user, student)
    
    def get(self, request, student_id, report_card_id=None):
        """Handle GET request for report card view"""
        try:
            student_id = int(student_id)
        except (ValueError, TypeError):
            raise Http404("Invalid student ID format")

        student = get_object_or_404(Student, pk=student_id)

        # Get report_card_id from URL or GET parameters
        report_card_id = report_card_id or request.GET.get('report_card_id')
        
        # Handle preview mode (when no report card exists yet)
        preview_mode = request.GET.get('preview') == 'true'
        create_new = request.GET.get('create_new') == 'true'
        
        # Get academic year and term from GET parameters or report card
        academic_year = request.GET.get('academic_year')
        term = request.GET.get('term')
        
        report_card = None
        if report_card_id:
            report_card = self._get_report_card(report_card_id, student)
            # If we have a report card, use its academic year and term
            if report_card:
                academic_year = report_card.academic_year
                term = report_card.term
        
        # If preview mode and no report card, show preview from grades
        if preview_mode and not report_card:
            if not all([academic_year, term]):
                messages.error(request, 'Academic year and term are required for preview')
                return redirect('report_card_dashboard')
            
            # Get grades for preview
            grades, aggregates = self._get_grade_data_preview(student, academic_year, term)
        else:
            # Get grades normally
            if report_card:
                grades, aggregates = self._get_grade_data(request, student, report_card)
            elif academic_year and term:
                # If we have academic year/term but no report card, show preview
                grades, aggregates = self._get_grade_data_preview(student, academic_year, term)
            else:
                # No report card and no academic year/term - show latest
                latest_grades = Grade.objects.filter(student=student).order_by('-academic_year', '-term').first()
                if latest_grades:
                    academic_year = latest_grades.academic_year
                    term = latest_grades.term
                    grades, aggregates = self._get_grade_data_preview(student, academic_year, term)
                else:
                    messages.error(request, 'No grades found for this student')
                    return redirect('report_card_dashboard')

        # Get attendance data using utils
        attendance_data = get_attendance_summary(student, aggregates['academic_year'], aggregates['term'])
        
        # Get additional information
        additional_info = self._get_additional_info(student, aggregates)

        # Check if we're in edit mode
        editable_mode = request.GET.get('editable') == 'true'
        
        # Get available subjects for adding new grades
        available_subjects = []
        if (is_teacher(request.user) or is_admin(request.user)) and editable_mode:
            available_subjects = Subject.objects.filter(
                class_level=student.class_level
            ).order_by('name')
        
        context = {
            'student': student,
            'grades': grades,
            'average_score': aggregates['average_score'],
            'overall_grade': aggregates['overall_grade'],
            'academic_year': aggregates['academic_year'],
            'term': aggregates['term'],
            'report_card': report_card,
            'form': ReportCardFilterForm(request.GET),
            'attendance': attendance_data,
            'vacation_date': additional_info['vacation_date'],
            'reopening_date': additional_info['reopening_date'],
            'position_in_class': additional_info['position_in_class'],
            'is_teacher': is_teacher(request.user),
            'is_admin': is_admin(request.user),
            'is_student': is_student(request.user),
            'is_parent': is_parent(request.user),
            # Edit mode context
            'editable_mode': editable_mode,
            'can_edit': is_teacher(request.user) or is_admin(request.user),
            'available_subjects': available_subjects,
        }

        return render(request, 'core/academics/report_cards/report_card.html', context)

    def post(self, request, student_id, report_card_id=None):
        """Handle POST requests for grade updates"""
        try:
            student = get_object_or_404(Student, pk=student_id)
            
            # Check if user can edit
            if not can_edit_grades(request.user, student):
                return JsonResponse({'success': False, 'error': 'Permission denied'})
            
            action = request.POST.get('action')
            
            if action == 'update_grade':
                return self._handle_grade_update(request, student)
            elif action == 'add_grade':
                return self._handle_add_grade(request, student)
            elif action == 'delete_grade':
                return self._handle_delete_grade(request, student)
            elif action == 'publish_report_card':
                return self._handle_publish_report_card(request, student, report_card_id)
            elif action == 'unpublish_report_card':
                return self._handle_unpublish_report_card(request, student, report_card_id)
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})
                
        except Exception as e:
            logger.error(f"Error in report card POST: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': str(e)})
    
    def _handle_grade_update(self, request, student):
        """Handle grade update"""
        grade_id = request.POST.get('grade_id')
        grade = get_object_or_404(Grade, pk=grade_id, student=student)
        
        # Update grade fields
        grade.homework_score = request.POST.get('homework', grade.homework_score)
        grade.classwork_score = request.POST.get('classwork', grade.classwork_score)
        grade.test_score = request.POST.get('test', grade.test_score)
        grade.exam_score = request.POST.get('exam', grade.exam_score)
        grade.remarks = request.POST.get('remarks', grade.remarks)
        
        # Calculate total using utils
        grade.total_score = calculate_total_score(
            grade.homework_score, grade.classwork_score,
            grade.test_score, grade.exam_score
        )
        
        # Update letter grade using utils
        grade.letter_grade = calculate_letter_grade(grade.total_score)
        
        grade.save()
        
        # Update report card if exists
        self._update_report_card_average(student, grade.academic_year, grade.term)
        
        return JsonResponse({
            'success': True,
            'message': 'Grade updated successfully',
            'total_score': float(grade.total_score),
            'letter_grade': grade.letter_grade,
            'grade_color': get_grade_color(grade.letter_grade)
        })
    
    def _handle_add_grade(self, request, student):
        """Handle adding new grade"""
        subject_id = request.POST.get('subject_id')
        subject = get_object_or_404(Subject, pk=subject_id)
        
        academic_year = request.POST.get('academic_year', get_current_academic_year())
        term = request.POST.get('term', 1)
        
        grade = Grade.objects.create(
            student=student,
            subject=subject,
            academic_year=academic_year,
            term=term,
            homework_score=request.POST.get('homework', 0),
            classwork_score=request.POST.get('classwork', 0),
            test_score=request.POST.get('test', 0),
            exam_score=request.POST.get('exam', 0),
            remarks=request.POST.get('remarks', ''),
            teacher=request.user.teacher if is_teacher(request.user) else None
        )
        
        # Calculate total and letter grade
        grade.total_score = calculate_total_score(
            grade.homework_score, grade.classwork_score,
            grade.test_score, grade.exam_score
        )
        grade.letter_grade = calculate_letter_grade(grade.total_score)
        grade.save()
        
        # Update report card
        self._update_report_card_average(student, academic_year, term)
        
        return JsonResponse({
            'success': True,
            'message': 'Grade added successfully',
            'grade_id': grade.id
        })
    
    def _handle_delete_grade(self, request, student):
        """Handle grade deletion"""
        grade_id = request.POST.get('grade_id')
        grade = get_object_or_404(Grade, pk=grade_id, student=student)
        
        academic_year = grade.academic_year
        term = grade.term
        grade.delete()
        
        # Update report card
        self._update_report_card_average(student, academic_year, term)
        
        return JsonResponse({
            'success': True,
            'message': 'Grade deleted successfully'
        })
    
    def _handle_publish_report_card(self, request, student, report_card_id):
        """Handle publishing report card"""
        report_card = get_object_or_404(ReportCard, pk=report_card_id, student=student)
        report_card.is_published = True
        report_card.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Report card published successfully'
        })
    
    def _handle_unpublish_report_card(self, request, student, report_card_id):
        """Handle unpublishing report card"""
        report_card = get_object_or_404(ReportCard, pk=report_card_id, student=student)
        report_card.is_published = False
        report_card.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Report card unpublished successfully'
        })
    
    def _update_report_card_average(self, student, academic_year, term):
        """Update report card average after grade changes"""
        report_card = ReportCard.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        ).first()
        
        if report_card:
            report_card.calculate_grades()
            report_card.save()
    
    def _get_report_card(self, report_card_id, student):
        """Get specific report card or return None"""
        if report_card_id:
            try:
                return get_object_or_404(ReportCard, pk=report_card_id, student=student)
            except (ValueError, TypeError):
                raise Http404("Invalid report card ID")
        return None
    
    def _get_grade_data_preview(self, student, academic_year, term):
        """Get grade data for preview mode (when no report card exists yet)"""
        grades = Grade.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        ).select_related('subject').order_by('subject__name')
        
        # Calculate aggregates
        aggregates = grades.aggregate(avg_score=Avg('total_score'))
        average_score = aggregates['avg_score'] or 0.0
        
        # Calculate overall grade using utils
        overall_grade = calculate_letter_grade(average_score)
        
        return grades, {
            'average_score': round(float(average_score), 2),
            'overall_grade': overall_grade,
            'academic_year': academic_year,
            'term': term,
        }
    
    def _get_grade_data(self, request, student, report_card=None):
        """Get filtered grades and calculate aggregates"""
        if report_card:
            # Use the academic year and term from the report card
            grades = Grade.objects.filter(
                student=student,
                academic_year=report_card.academic_year,
                term=report_card.term
            )
            academic_year = report_card.academic_year
            term = report_card.term
        else:
            # Apply filters from GET parameters
            grades = Grade.objects.filter(student=student)
            form = ReportCardFilterForm(request.GET)
            if form.is_valid():
                if form.cleaned_data.get('academic_year'):
                    grades = grades.filter(academic_year=form.cleaned_data['academic_year'])
                if form.cleaned_data.get('term'):
                    grades = grades.filter(term=form.cleaned_data['term'])
            
            # Get academic year and term from grades or use defaults
            if grades.exists():
                academic_year = grades[0].academic_year
                term = grades[0].term
            else:
                # Use current academic year and term as fallback
                current_year = timezone.now().year
                academic_year = f"{current_year}/{current_year + 1}"
                term = 1
        
        grades = grades.select_related('subject').order_by('subject__name')
        
        # Calculate aggregates
        aggregates = grades.aggregate(avg_score=Avg('total_score'))
        
        average_score = aggregates['avg_score']
        if average_score is None:
            average_score = 0.0
        
        # Calculate overall grade using utils
        overall_grade = calculate_letter_grade(average_score)
        
        return grades, {
            'average_score': round(float(average_score), 2),
            'overall_grade': overall_grade,
            'academic_year': academic_year,
            'term': term,
        }
    
    def _get_additional_info(self, student, aggregates):
        """Get additional information like vacation dates and class position"""
        try:
            # Get academic term for vacation and reopening dates
            academic_term = AcademicTerm.objects.filter(
                academic_year=aggregates['academic_year'],
                term=aggregates['term']
            ).first()
            
            vacation_date = academic_term.end_date if academic_term else None
            reopening_date = self._calculate_reopening_date(academic_term) if academic_term else None
            
            # Calculate position in class using utils
            position_in_class = get_student_position_in_class(
                student, aggregates['academic_year'], aggregates['term']
            )
            
            return {
                'vacation_date': format_date(vacation_date) if vacation_date else "To be announced",
                'reopening_date': format_date(reopening_date) if reopening_date else "To be announced",
                'position_in_class': position_in_class,
            }
        except Exception as e:
            logger.error(f"Error getting additional info for student {student.id}: {str(e)}")
            return {
                'vacation_date': "To be announced",
                'reopening_date': "To be announced",
                'position_in_class': "Not ranked",
            }
    
    def _calculate_reopening_date(self, academic_term):
        """Calculate reopening date (next term start date)"""
        try:
            if not academic_term:
                return None
                
            # Try to find next term in the same academic year
            next_term = AcademicTerm.objects.filter(
                academic_year=academic_term.academic_year,
                term=academic_term.term + 1
            ).first()
            
            if next_term:
                return next_term.start_date
            
            # If no next term in same academic year, calculate for next academic year
            next_academic_year = self._get_next_academic_year(academic_term.academic_year)
            next_term = AcademicTerm.objects.filter(
                academic_year=next_academic_year,
                term=1
            ).first()
            
            return next_term.start_date if next_term else None
            
        except Exception as e:
            logger.error(f"Error calculating reopening date: {str(e)}")
            return None
    
    def _get_next_academic_year(self, academic_year):
        """Get next academic year from current academic year string"""
        try:
            years = academic_year.split('/')
            if len(years) == 2:
                current_year = int(years[0])
                return f"{current_year + 1}/{current_year + 2}"
        except:
            pass
        
        # Fallback: calculate from current date
        current_year = timezone.now().year
        return f"{current_year + 1}/{current_year + 2}"


class ReportCardPDFView(LoginRequiredMixin, View):
    """
    Enhanced PDF view with all new information included
    """
    
    def get(self, request, student_id, report_card_id=None):
        student = get_object_or_404(Student, pk=student_id)
        
        # Check permissions using utils
        if not check_report_card_permission(request.user, student):
            raise PermissionDenied("You don't have permission to view this report card")
        
        # Get grades and determine academic year/term
        if report_card_id:
            report_card = get_object_or_404(ReportCard, pk=report_card_id, student=student)
            academic_year = report_card.academic_year
            term = report_card.term
            grades = Grade.objects.filter(
                student=student,
                academic_year=academic_year,
                term=term
            )
        else:
            # Use GET parameters or defaults
            academic_year = request.GET.get('academic_year')
            term = request.GET.get('term')
            
            grades = Grade.objects.filter(student=student)
            if academic_year:
                grades = grades.filter(academic_year=academic_year)
            if term:
                grades = grades.filter(term=term)
            
            if grades.exists():
                academic_year = grades[0].academic_year
                term = grades[0].term
            else:
                # Use current academic year and term as fallback
                current_year = timezone.now().year
                academic_year = f"{current_year}/{current_year + 1}"
                term = 1
        
        grades = grades.select_related('subject').order_by('subject__name')
        
        # Calculate aggregates
        aggregates = grades.aggregate(avg_score=Avg('total_score'))
        average_score = aggregates['avg_score'] or 0.0
        overall_grade = calculate_letter_grade(average_score)
        
        # Get attendance data using utils
        attendance_data = get_attendance_summary(student, academic_year, term)
        
        # Get additional information
        additional_info = self._get_additional_info(student, academic_year, term)
        
        # Get school configuration
        school_config = SchoolConfiguration.get_config()
        
        # Create PDF response
        response = HttpResponse(content_type='application/pdf')
        filename = f"Report_Card_{student.student_id}_{academic_year}_Term{term}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Create the PDF object
        doc = SimpleDocTemplate(
            response,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Add content to PDF
        self._create_pdf_header(elements, student, academic_year, term, school_config)
        self._create_additional_info_section(elements, additional_info)
        self._create_attendance_section(elements, attendance_data)
        self._create_student_info_section(elements, student)
        self._create_grades_table(elements, grades)
        self._create_summary_section(elements, average_score, overall_grade)
        self._create_signature_section(elements)
        
        # Build PDF
        doc.build(elements)
        return response
    
    def _get_additional_info(self, student, academic_year, term):
        """Get additional information for PDF"""
        try:
            academic_term = AcademicTerm.objects.filter(
                academic_year=academic_year,
                term=term
            ).first()
            
            vacation_date = academic_term.end_date if academic_term else None
            reopening_date = self._calculate_reopening_date(academic_term) if academic_term else None
            
            # Get class position using utils
            position_in_class = get_student_position_in_class(student, academic_year, term)
            
            return {
                'vacation_date': format_date(vacation_date) if vacation_date else "To be announced",
                'reopening_date': format_date(reopening_date) if reopening_date else "To be announced",
                'position_in_class': position_in_class,
            }
        except Exception as e:
            logger.error(f"Error getting additional info for PDF: {str(e)}")
            return {
                'vacation_date': "To be announced",
                'reopening_date': "To be announced",
                'position_in_class': "Not ranked",
            }
    
    def _calculate_reopening_date(self, academic_term):
        """Calculate reopening date for PDF"""
        try:
            if not academic_term:
                return None
                
            next_term = AcademicTerm.objects.filter(
                academic_year=academic_term.academic_year,
                term=academic_term.term + 1
            ).first()
            
            if next_term:
                return next_term.start_date
            
            next_academic_year = self._get_next_academic_year(academic_term.academic_year)
            next_term = AcademicTerm.objects.filter(
                academic_year=next_academic_year,
                term=1
            ).first()
            
            return next_term.start_date if next_term else None
        except Exception as e:
            logger.error(f"Error calculating reopening date for PDF: {str(e)}")
            return None
    
    def _get_next_academic_year(self, academic_year):
        """Get next academic year"""
        try:
            years = academic_year.split('/')
            if len(years) == 2:
                current_year = int(years[0])
                return f"{current_year + 1}/{current_year + 2}"
        except:
            pass
        
        current_year = timezone.now().year
        return f"{current_year + 1}/{current_year + 2}"
    
    def _create_pdf_header(self, elements, student, academic_year, term, school_config):
        """Create PDF header section"""
        styles = getSampleStyleSheet()
        
        # School name
        school_style = ParagraphStyle(
            'SchoolStyle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            alignment=1,  # Center aligned
        )
        elements.append(Paragraph(school_config.school_name, school_style))
        
        # Report card title
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=6,
            alignment=1,
        )
        elements.append(Paragraph("OFFICIAL ACADEMIC REPORT CARD", title_style))
        
        # Academic year and term
        year_style = ParagraphStyle(
            'YearStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=12,
            alignment=1,
        )
        elements.append(Paragraph(f"{academic_year} - Term {term}", year_style))
        
        elements.append(Spacer(1, 12))
    
    def _create_additional_info_section(self, elements, additional_info):
        """Create additional information section in PDF"""
        styles = getSampleStyleSheet()
        
        # Section title
        title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=6,
            textColor=colors.HexColor('#2c3e50'),
        )
        elements.append(Paragraph("Academic Calendar Information", title_style))
        
        # Information table
        info_data = [
            ['Vacation Date:', additional_info['vacation_date']],
            ['Reopening Date:', additional_info['reopening_date']],
            ['Position in Class:', additional_info['position_in_class']],
        ]
        
        info_table = Table(info_data, colWidths=[100, 200])
        info_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 12))
    
    def _create_attendance_section(self, elements, attendance_data):
        """Create attendance section in PDF"""
        styles = getSampleStyleSheet()
        
        # Section title
        title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=6,
            textColor=colors.HexColor('#2c3e50'),
        )
        elements.append(Paragraph("Attendance Summary", title_style))
        
        # Attendance table
        attendance_info = [
            ['Days Present:', str(attendance_data['present_days'])],
            ['Total Days:', str(attendance_data['total_days'])],
            ['Attendance Rate:', f"{attendance_data['attendance_rate']}%"],
            ['Days Absent:', str(attendance_data['absence_count'])],
        ]
        
        attendance_table = Table(attendance_info, colWidths=[100, 80])
        attendance_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fff3e0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(attendance_table)
        elements.append(Spacer(1, 12))
    
    def _create_student_info_section(self, elements, student):
        """Create student information section"""
        styles = getSampleStyleSheet()
        
        # Section title
        title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=6,
            textColor=colors.HexColor('#2c3e50'),
        )
        elements.append(Paragraph("Student Information", title_style))
        
        # Student info table
        student_info = [
            ['Student Name:', student.get_full_name()],
            ['Student ID:', student.student_id],
            ['Class Level:', get_class_level_display(student.class_level)],
            ['Gender:', student.get_gender_display()],
        ]
        
        student_table = Table(student_info, colWidths=[100, 200])
        student_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(student_table)
        elements.append(Spacer(1, 12))
    
    def _create_grades_table(self, elements, grades):
        """Create grades table in PDF"""
        styles = getSampleStyleSheet()
        
        # Section title
        title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=6,
            textColor=colors.HexColor('#2c3e50'),
        )
        elements.append(Paragraph("Academic Performance", title_style))
        
        # Table headers
        headers = ['Subject', 'Homework', 'Classwork', 'Test', 'Exam', 'Total', 'Grade']
        
        # Table data
        table_data = [headers]
        
        for grade in grades:
            row = [
                grade.subject.name,
                f"{grade.homework_score or 0:.1f}",
                f"{grade.classwork_score or 0:.1f}",
                f"{grade.test_score or 0:.1f}",
                f"{grade.exam_score or 0:.1f}",
                f"{grade.total_score or 0:.1f}",
                grade.letter_grade or "N/A"
            ]
            table_data.append(row)
        
        # Create table
        grades_table = Table(table_data, colWidths=[120, 60, 60, 50, 50, 50, 40])
        grades_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),  # Header row
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),      # Data rows
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),  # Header background
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  # Header text color
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))
        
        elements.append(grades_table)
        elements.append(Spacer(1, 12))
    
    def _create_summary_section(self, elements, average_score, overall_grade):
        """Create summary section in PDF"""
        styles = getSampleStyleSheet()
        
        # Section title
        title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=6,
            textColor=colors.HexColor('#2c3e50'),
        )
        elements.append(Paragraph("Performance Summary", title_style))
        
        # Summary table
        summary_data = [
            ['Overall Average:', f"{average_score:.1f}%"],
            ['Final Grade:', overall_grade],
            ['Performance Level:', get_performance_level(average_score)],
        ]
        
        summary_table = Table(summary_data, colWidths=[100, 80, 120])
        summary_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', 10),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 12))
    
    def _create_signature_section(self, elements):
        """Create signature section in PDF"""
        styles = getSampleStyleSheet()
        
        # Signature table
        signature_data = [
            ['Class Teacher', 'Head of Department', 'School Principal'],
            ['_________________________', '_________________________', '_________________________'],
            ['Signature & Date', 'Signature & Date', 'Signature & Date'],
        ]
        
        signature_table = Table(signature_data, colWidths=[150, 150, 150])
        signature_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(signature_table)


class SaveReportCardView(LoginRequiredMixin, View):
    """
    View for saving report cards from preview mode
    """
    
    def post(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        
        if not is_teacher(request.user):
            raise PermissionDenied("Only teachers can save report cards")
        
        academic_year = request.POST.get('academic_year')
        term = request.POST.get('term')
        
        # Validate academic year format using utils
        is_valid, error_message = validate_academic_year(academic_year)
        if not is_valid:
            messages.error(request, error_message)
            return redirect('report_card', student_id=student_id)
        
        # Validate term
        try:
            term = int(term)
            if term not in [1, 2, 3]:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Invalid term. Must be 1, 2, or 3.')
            return redirect('report_card', student_id=student_id)
        
        # Create or get the report card
        report_card, created = ReportCard.objects.get_or_create(
            student=student,
            academic_year=academic_year,
            term=term,
            defaults={
                'is_published': False,
                'created_by': request.user
            }
        )
        
        # Calculate grades
        report_card.calculate_grades()
        report_card.save()
        
        if created:
            messages.success(request, 'Report card created successfully!')
        else:
            messages.info(request, 'Report card already exists and has been updated.')
        
        return redirect('report_card_detail', student_id=student_id, report_card_id=report_card.id)


class QuickViewReportCardPDFView(LoginRequiredMixin, View):
    """
    PDF view for quick view report cards
    """
    
    def get(self, request):
        student_id = request.GET.get('student_id')
        academic_year = request.GET.get('academic_year')
        term = request.GET.get('term')
        
        if not all([student_id, academic_year, term]):
            messages.error(request, 'Student, academic year, and term are required')
            return redirect('report_card_dashboard')
        
        try:
            student = get_object_or_404(Student, pk=student_id)
            
            # Check permissions
            if not check_report_card_permission(request.user, student):
                raise PermissionDenied("You don't have permission to view this report card")
            
            # Redirect to the existing PDF view
            return redirect(reverse('report_card_pdf', kwargs={'student_id': student_id}) + 
                           f'?academic_year={academic_year}&term={term}')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('report_card_dashboard')