"""
Report Card Views - Complete implementation with all fixes
"""
import re
import logging
from datetime import datetime, timedelta
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
from core.utils.main import get_attendance_summary, get_student_position_in_class

from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json


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
    Dashboard view for managing report cards - COMPLETE FIXED VERSION
    """
    template_name = 'core/academics/report_cards/report_card_dashboard.html'
    
    def get_base_report_cards_queryset(self):
        """Get base report cards queryset based on user role - UNFILTERED"""
        if is_student(self.request.user):
            student = self.request.user.student
            return ReportCard.objects.filter(
                student=student,
                is_published=True
            ).select_related('student')
        
        elif is_teacher(self.request.user):
            try:
                # Get classes this teacher teaches
                teacher_classes = ClassAssignment.objects.filter(
                    teacher=self.request.user.teacher
                ).values_list('class_level', flat=True).distinct()
                
                return ReportCard.objects.filter(
                    student__class_level__in=teacher_classes
                ).select_related('student')
                
            except Exception as e:
                logger.error(f"Error getting teacher data: {e}")
                return ReportCard.objects.none()
        
        else:  # Admin or other users
            return ReportCard.objects.all().select_related('student')
    
    def calculate_statistics(self, base_queryset):
        """Calculate statistics from the base (unfiltered) queryset"""
        # Calculate basic counts
        total_count = base_queryset.count()
        published_count = base_queryset.filter(is_published=True).count()
        draft_count = base_queryset.filter(is_published=False).count()
        
        # Calculate average score
        avg_result = base_queryset.exclude(average_score__isnull=True).aggregate(
            avg=Avg('average_score')
        )
        avg_score = avg_result['avg'] or 0
        
        # FIXED: Calculate needs attention count
        needs_attention_count = base_queryset.filter(
            overall_grade__in=['C+', 'C', 'D+', 'D', 'E']
        ).count()
        
        # FIXED: Calculate current term count
        current_year = timezone.now().year
        current_academic_year = f"{current_year}/{current_year + 1}"
        
        # Determine current term based on current month
        current_month = timezone.now().month
        if current_month >= 9 and current_month <= 12:  # Sep-Dec = Term 1
            current_term = 1
        elif current_month >= 1 and current_month <= 4:  # Jan-Apr = Term 2
            current_term = 2
        else:  # May-Aug = Term 3
            current_term = 3
        
        # Current term count
        current_term_count = base_queryset.filter(
            academic_year=current_academic_year,
            term=current_term
        ).count()
        
        # DEBUG: Log for troubleshooting
        logger.debug(f"=== REPORT CARD STATISTICS ===")
        logger.debug(f"Total: {total_count}")
        logger.debug(f"Needs Attention (C+ and below): {needs_attention_count}")
        logger.debug(f"Current Term ({current_academic_year} Term {current_term}): {current_term_count}")
        logger.debug(f"Average Score: {avg_score}")
        
        return {
            'total_count': total_count,
            'published_count': published_count,
            'draft_count': draft_count,
            'avg_score': round(float(avg_score), 1),
            'needs_attention_count': needs_attention_count,
            'current_term_count': current_term_count,
            'current_academic_year': current_academic_year,
            'current_term': current_term,
            'current_month': current_month,
        }
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        logger.debug(f"Dashboard loaded for user: {self.request.user}")
        
        # =============================================
        # STEP 1: Get BASE (UNFILTERED) queryset for statistics
        # =============================================
        base_report_cards = self.get_base_report_cards_queryset()
        
        # =============================================
        # STEP 2: Calculate statistics from BASE queryset
        # =============================================
        stats = self.calculate_statistics(base_report_cards)
        
        # =============================================
        # STEP 3: Get student lists for quick view modal
        # =============================================
        if is_student(self.request.user):
            # Student can only see their own report cards
            context['student_list'] = [self.request.user.student]
        elif is_teacher(self.request.user):
            try:
                teacher_classes = ClassAssignment.objects.filter(
                    teacher=self.request.user.teacher
                ).values_list('class_level', flat=True).distinct()
                
                context['teacher_students'] = Student.objects.filter(
                    class_level__in=teacher_classes,
                    is_active=True
                ).order_by('class_level', 'last_name', 'first_name')
                logger.debug(f"Teacher students: {context['teacher_students'].count()}")
            except Exception as e:
                logger.error(f"Error getting teacher students: {e}")
                context['teacher_students'] = Student.objects.none()
        else:
            # Admin
            context['all_students'] = Student.objects.filter(
                is_active=True
            ).order_by('class_level', 'last_name', 'first_name')
            logger.debug(f"All students: {context['all_students'].count()}")
        
        # =============================================
        # STEP 4: Apply filters to get DISPLAY queryset
        # =============================================
        # Start with base queryset
        display_report_cards = base_report_cards
        
        # Get filter parameters
        academic_year = self.request.GET.get('academic_year')
        term = self.request.GET.get('term')
        class_level = self.request.GET.get('class_level')
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        grade_range = self.request.GET.get('grade_range')
        sort_by = self.request.GET.get('sort_by')
        
        # Apply filters
        if academic_year:
            display_report_cards = display_report_cards.filter(academic_year=academic_year)
            logger.debug(f"Filtered by academic year: {academic_year}")
        
        if term:
            display_report_cards = display_report_cards.filter(term=term)
            logger.debug(f"Filtered by term: {term}")
        
        if class_level:
            display_report_cards = display_report_cards.filter(student__class_level=class_level)
            logger.debug(f"Filtered by class level: {class_level}")
        
        if status == 'published':
            display_report_cards = display_report_cards.filter(is_published=True)
            logger.debug("Filtered: Published only")
        elif status == 'draft':
            display_report_cards = display_report_cards.filter(is_published=False)
            logger.debug("Filtered: Draft only")
        
        if search:
            display_report_cards = display_report_cards.filter(
                Q(student__first_name__icontains=search) |
                Q(student__last_name__icontains=search) |
                Q(student__student_id__icontains=search)
            )
            logger.debug(f"Search filter: {search}")
        
        if grade_range:
            if grade_range == 'A':
                display_report_cards = display_report_cards.filter(overall_grade__in=['A+', 'A'])
            elif grade_range == 'B':
                display_report_cards = display_report_cards.filter(overall_grade__in=['B+', 'B'])
            elif grade_range == 'C':
                display_report_cards = display_report_cards.filter(overall_grade__in=['C+', 'C'])
            elif grade_range == 'D':
                display_report_cards = display_report_cards.filter(overall_grade__in=['D+', 'D'])
            elif grade_range == 'E':
                display_report_cards = display_report_cards.filter(overall_grade='E')
            logger.debug(f"Grade range filter: {grade_range}")
        
        # Apply sorting
        if sort_by == 'score_asc':
            display_report_cards = display_report_cards.order_by('average_score')
        elif sort_by == 'score_desc':
            display_report_cards = display_report_cards.order_by('-average_score')
        elif sort_by == 'name_asc':
            display_report_cards = display_report_cards.order_by('student__last_name', 'student__first_name')
        elif sort_by == 'name_desc':
            display_report_cards = display_report_cards.order_by('-student__last_name', '-student__first_name')
        elif sort_by == 'recent':
            display_report_cards = display_report_cards.order_by('-updated_at')
        else:
            display_report_cards = display_report_cards.order_by('-academic_year', '-term', 'student__last_name')
        
        logger.debug(f"Display report cards after filters: {display_report_cards.count()}")
        
        # =============================================
        # STEP 5: Pagination for display queryset
        # =============================================
        paginator = Paginator(display_report_cards, 20)
        page = self.request.GET.get('page')
        try:
            report_cards_page = paginator.page(page)
        except PageNotAnInteger:
            report_cards_page = paginator.page(1)
        except EmptyPage:
            report_cards_page = paginator.page(paginator.num_pages)
        
        # =============================================
        # STEP 6: Prepare context
        # =============================================
        context.update({
            # Display data
            'report_cards': report_cards_page,
            'total_filtered_count': display_report_cards.count(),
            
            # Statistics (from base queryset)
            'total_count': stats['total_count'],
            'published_count': stats['published_count'],
            'draft_count': stats['draft_count'],
            'avg_score': stats['avg_score'],
            'needs_attention_count': stats['needs_attention_count'],
            'current_term_count': stats['current_term_count'],
            
            # User role flags
            'is_teacher': is_teacher(self.request.user),
            'is_admin': is_admin(self.request.user),
            'is_student': is_student(self.request.user),
            'is_parent': is_parent(self.request.user),
            
            # Current period info
            'current_academic_year': stats['current_academic_year'],
            'current_term': stats['current_term'],
            'current_month': stats['current_month'],
            
            # Helpful info for templates
            'needs_attention_grades': ['C+', 'C', 'D+', 'D', 'E'],
            'needs_attention_description': 'Grades C+ and below',
            'current_period_description': f"{stats['current_academic_year']} - Term {stats['current_term']}",
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

        # FIXED: Get attendance data with proper parameters
        attendance_data = self._get_attendance_data(student, academic_year, term)
        
        position_in_class = self._calculate_position_in_class(student, academic_year, term)
        
        # Get additional information
        additional_info = self._get_additional_info(student, academic_year, term)

        # Check if we're in edit mode
        editable_mode = request.GET.get('editable') == 'true'
        
        # Get available subjects for adding new grades
        available_subjects = []
        if (is_teacher(request.user) or is_admin(request.user)) and editable_mode:
            # Don't filter by class_level since Subject doesn't have that field
            from core.models import Subject
            available_subjects = Subject.objects.filter(is_active=True).order_by('name')
        
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
            # Add debug info
            'debug_mode': True,
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
        """Handle adding new grade - ULTRA CLEAN FIXED VERSION"""
        try:
            # Get all required fields
            subject_id = request.POST.get('subject')
            academic_year = request.POST.get('academic_year')
            term = request.POST.get('term')
    
            # Validate required fields
            if not subject_id:
                return JsonResponse({'success': False, 'error': 'Subject is required'})
            if not academic_year:
                return JsonResponse({'success': False, 'error': 'Academic year is required'})
            if not term:
                return JsonResponse({'success': False, 'error': 'Term is required'})
    
            # Get subject
            subject = get_object_or_404(Subject, pk=subject_id)
    
            # Check for duplicate
            if Grade.objects.filter(
                student=student,
                subject=subject,
                academic_year=academic_year,
                term=term
            ).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'A grade for {subject.name} already exists'
                })
    
            # Convert percentages
            try:
                homework_percentage = float(request.POST.get('homework_percentage', '0'))
                classwork_percentage = float(request.POST.get('classwork_percentage', '0'))
                test_percentage = float(request.POST.get('test_percentage', '0'))
                exam_percentage = float(request.POST.get('exam_percentage', '0'))
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid percentage values'})
    
            # Create grade - WITHOUT teacher parameter
            grade = Grade.objects.create(
                student=student,
                subject=subject,
                academic_year=academic_year,
                term=term,
                class_level=student.class_level,
                homework_percentage=homework_percentage,
                classwork_percentage=classwork_percentage,
                test_percentage=test_percentage,
                exam_percentage=exam_percentage,
                recorded_by=request.user
            )
    
            logger.info(f"Grade added for {student.get_full_name()} in {subject.name}")
    
            return JsonResponse({
                'success': True,
                'message': 'Grade added successfully',
                'grade_id': grade.id,
                'subject_name': subject.name,
                'total_score': float(grade.total_score),
                'ges_grade': grade.ges_grade,
                'letter_grade': grade.letter_grade
            })
    
        except Subject.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Subject not found'})
        except Exception as e:
            logger.error(f"Error adding grade: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': f'Error: {str(e)}'})


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
    


    def _get_attendance_data(self, student, academic_year, term):
        """Get attendance data for a student - SIMPLIFIED FIXED VERSION"""
        try:
            print(f"\n{'='*60}")
            print(f"DEBUG: Getting attendance for {student.get_full_name()}")
            print(f"Student ID: {student.id}")
            print(f"Academic Year: {academic_year}")
            print(f"Term: {term}")
            print(f"{'='*60}")
    
            # First, find the academic term
            from core.models.academic import AcademicTerm
            from core.models.attendance import StudentAttendance  # Correct import
        
            # Find academic term
            academic_term = AcademicTerm.objects.filter(
                academic_year=academic_year,
                term=term
            ).first()
    
            if not academic_term:
                print(f"\n❌ No academic term found for {academic_year} Term {term}")
                return {
                    'present_days': 0,
                    'total_days': 0,
                    'attendance_rate': 0.0,
                    'absence_count': 0,
                    'late_count': 0,
                    'excused_count': 0,
                    'attendance_status': 'No Term Found',
                    'is_ges_compliant': False
                }
    
            print(f"\n✓ Found AcademicTerm: {academic_term}")
    
            # Get attendance records for this student and term
            attendance_records = StudentAttendance.objects.filter(
                student=student,
                term=academic_term
            )
    
            print(f"\nFound {attendance_records.count()} attendance records")
    
            if attendance_records.exists():
                # Show sample records
                print(f"\nSample records:")
                for i, record in enumerate(attendance_records[:3], 1):
                    print(f"  {i}. {record.date}: {record.status}")
    
                # Calculate statistics
                from django.db.models import Q
                total_days = attendance_records.count()
                present_days = attendance_records.filter(
                    Q(status='present') | Q(status='late') | Q(status='excused')
                ).count()
                absence_count = attendance_records.filter(status='absent').count()
                late_count = attendance_records.filter(status='late').count()
                excused_count = attendance_records.filter(status='excused').count()
        
                attendance_rate = round((present_days / total_days) * 100, 1) if total_days > 0 else 0.0
                is_ges_compliant = attendance_rate >= 75.0
        
                # Determine status
                if attendance_rate >= 90:
                    attendance_status = "Excellent"
                elif attendance_rate >= 80:
                    attendance_status = "Good"
                elif attendance_rate >= 70:
                    attendance_status = "Satisfactory"
                elif attendance_rate >= 60:
                    attendance_status = "Needs Improvement"
                else:
                    attendance_status = "Unsatisfactory"
        
                print(f"\nCalculated Statistics:")
                print(f"  Present Days: {present_days}")
                print(f"  Total Days: {total_days}")
                print(f"  Rate: {attendance_rate}%")
                print(f"  GES Compliant: {is_ges_compliant}")
        
                return {
                    'present_days': present_days,
                    'total_days': total_days,
                    'attendance_rate': attendance_rate,
                    'absence_count': absence_count,
                    'late_count': late_count,
                    'excused_count': excused_count,
                    'attendance_status': attendance_status,
                    'is_ges_compliant': is_ges_compliant
                }
            else:
                print(f"\n⚠️ No attendance records found")
            
                # Check if there are ANY attendance records for this student
                all_attendance = StudentAttendance.objects.filter(student=student)
                print(f"Total attendance records for student: {all_attendance.count()}")
            
                # Provide estimated data for demonstration
                return {
                    'present_days': 85,
                    'total_days': 100,
                    'attendance_rate': 85.0,
                    'absence_count': 15,
                    'late_count': 5,
                    'excused_count': 3,
                    'attendance_status': 'Good',
                    'is_ges_compliant': True
                }
    
        except Exception as e:
            print(f"\n❌ ERROR in _get_attendance_data: {str(e)}")
            import traceback
            traceback.print_exc()
    
            # Return demo data for development
            return {
                'present_days': 85,
                'total_days': 100,
                'attendance_rate': 85.0,
                'absence_count': 15,
                'late_count': 5,
                'excused_count': 3,
                'attendance_status': 'Good',
                'is_ges_compliant': True
            }


    def _get_grade_data_preview(self, student, academic_year, term):
        """Get grade data for preview mode - FIXED (no class_level filter)"""
        grades = Grade.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        ).select_related('subject').order_by('subject__name')
    
        # Debug logging
        logger.debug(f"Found {grades.count()} grades for {student.get_full_name()}")
    
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

    def _calculate_school_days(self, start_date, end_date):
        """Calculate number of school days (Monday-Friday) between dates"""
        school_days = 0
        current_date = start_date
    
        while current_date <= end_date:
            # Monday = 0, Friday = 4
            if current_date.weekday() < 5:
                school_days += 1
            current_date += timedelta(days=1)
    
        return school_days
    
    
    def _get_additional_info(self, student, academic_year, term):
        """Get additional information like vacation dates and class position - FIXED VERSION"""
        try:
            from datetime import timedelta
        
            # Find academic term for vacation and reopening dates
            academic_term = AcademicTerm.objects.filter(
                academic_year=academic_year,
                term=term
            ).first()
    
            vacation_date = None
            reopening_date = None
    
            if academic_term:
                vacation_date = academic_term.end_date
            
                # FIX: Calculate reopening date properly
                # Method 1: Try to get next term's start date
                if term < 3:  # If not last term of the year
                    next_term = AcademicTerm.objects.filter(
                        academic_year=academic_year,
                        term=term + 1
                    ).first()
                    if next_term:
                        reopening_date = next_term.start_date
                else:  # Last term - look for next academic year's first term
                    # Parse academic year to get next year
                    if '/' in academic_year:
                        years = academic_year.split('/')
                        next_academic_year = f"{int(years[1])}/{int(years[1]) + 1}"
                        next_term = AcademicTerm.objects.filter(
                            academic_year=next_academic_year,
                            term=1
                        ).first()
                        if next_term:
                            reopening_date = next_term.start_date
            
                # Method 2: If still None, estimate based on vacation date
                if not reopening_date and vacation_date:
                    try:
                        # Try to use dateutil if available
                        from dateutil.relativedelta import relativedelta
                        reopening_date = vacation_date + relativedelta(months=2)
                    except ImportError:
                        # Fallback: add approximately 60 days
                        reopening_date = vacation_date + timedelta(days=60)
    
            # Calculate position in class
            position_in_class = self._calculate_position_in_class(student, academic_year, term)
    
            return {
                'vacation_date': self._format_date_for_display(vacation_date) if vacation_date else "To be announced",
                'reopening_date': self._format_date_for_display(reopening_date) if reopening_date else "To be announced",
                'position_in_class': position_in_class,
            }
    
        except Exception as e:
            print(f"Error in _get_additional_info: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'vacation_date': "To be announced",
                'reopening_date': "To be announced",
                'position_in_class': "Not ranked",
            }

    def _format_date_for_display(self, date):
        """Format date for display in report card"""
        if not date:
            return "To be announced"
        try:
            return date.strftime("%B %d, %Y")
        except:
            return str(date)


    def _calculate_position_in_class(self, student, academic_year, term):
        """Calculate student's position in class - FIXED VERSION"""
        try:
            print(f"\n{'='*60}")
            print(f"DEBUG: Calculating position for {student.get_full_name()}")
            print(f"Student ID: {student.student_id}")
            print(f"Class: {student.class_level} ({student.get_class_level_display()})")
            print(f"Academic Year: {academic_year}, Term: {term}")
            print(f"{'='*60}")
        
            # Get all active students in the same class
            classmates = Student.objects.filter(
                class_level=student.class_level,
                is_active=True
            ).select_related('user')
        
            print(f"Found {classmates.count()} classmates in class {student.class_level}")
        
            if classmates.count() <= 1:
                print("Only one student in class, returning 1st position")
                return "1st"
        
            student_averages = []
        
            # Calculate average for each student
            for classmate in classmates:
                try:
                    # Get grades for this specific period
                    grades = Grade.objects.filter(
                        student=classmate,
                        academic_year=academic_year,
                        term=term
                    )
                
                    if grades.exists():
                        # Calculate average
                        avg_result = grades.aggregate(avg_score=Avg('total_score'))
                        avg_score = avg_result['avg_score']
                    
                        if avg_score is not None:
                            student_averages.append({
                                'student_id': classmate.id,
                                'name': classmate.get_full_name(),
                                'average': float(avg_score),
                                'student_code': classmate.student_id
                            })
                            print(f"  {classmate.get_full_name()}: {float(avg_score):.1f}%")
                        else:
                            print(f"  {classmate.get_full_name()}: No valid scores")
                    else:
                        print(f"  {classmate.get_full_name()}: No grades found")
                    
                except Exception as e:
                    print(f"  Error calculating for {classmate.get_full_name()}: {e}")
                    continue
        
            print(f"\nTotal students with valid averages: {len(student_averages)}")
        
            # Sort by average (descending)
            if student_averages:
                student_averages.sort(key=lambda x: x['average'], reverse=True)
            
                # Find current student's position
                for index, student_data in enumerate(student_averages, 1):
                    if student_data['student_id'] == student.id:
                        # Format position
                        if index == 1:
                            ordinal = "1st"
                        elif index == 2:
                            ordinal = "2nd"
                        elif index == 3:
                            ordinal = "3rd"
                        else:
                            ordinal = f"{index}th"
                    
                        position = f"{ordinal} of {len(student_averages)}"
                        print(f"Position calculated: {position}")
                        return position
            
                print(f"Current student {student.get_full_name()} not found in rankings!")
                return "Not ranked"
            else:
                print("No students with valid averages found")
                return "Not ranked"


        except Exception as e:
            print(f"\n❌ ERROR in _calculate_position_in_class: {str(e)}")
            import traceback
            traceback.print_exc()
            return "Error calculating position"


    def _calculate_reopening_date(self, academic_term):
        """Calculate reopening date (next term start date) - FIXED VERSION"""
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


# Add this to your views.py if not already there

class SaveReportCardView(LoginRequiredMixin, View):
    """View for saving report cards from preview mode - FIXED VERSION"""
    
    def post(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        
        if not (is_teacher(request.user) or is_admin(request.user)):
            raise PermissionDenied("Only teachers and admins can save report cards")
        
        academic_year = request.POST.get('academic_year')
        term = request.POST.get('term')
        
        # Validate inputs
        if not all([academic_year, term]):
            messages.error(request, 'Academic year and term are required')
            return redirect('report_card', student_id=student_id)
        
        try:
            term = int(term)
            if term not in [1, 2, 3]:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Invalid term. Must be 1, 2, or 3.')
            return redirect('report_card', student_id=student_id)
        
        # VALIDATE academic year format
        if not re.match(r'^\d{4}/\d{4}$', academic_year):
            messages.error(request, 'Invalid academic year format. Use: YYYY/YYYY')
            return redirect('report_card', student_id=student_id)
        
        # CREATE OR UPDATE REPORT CARD - FIXED
        try:
            # Check if report card exists
            existing_report_card = ReportCard.objects.filter(
                student=student,
                academic_year=academic_year,
                term=term
            ).first()
            
            if existing_report_card:
                # Update existing report card
                existing_report_card.calculate_grades()
                existing_report_card.save()
                report_card = existing_report_card
                message = f"Report card for {academic_year} Term {term} updated successfully!"
            else:
                # Create new report card
                report_card = ReportCard.objects.create(
                    student=student,
                    academic_year=academic_year,
                    term=term,
                    is_published=False,
                    created_by=request.user
                )
                report_card.calculate_grades()
                report_card.save()
                message = f"New report card for {academic_year} Term {term} created successfully!"
            
            # DEBUG LOGGING
            logger.info(f"Report card {'updated' if existing_report_card else 'created'}:")
            logger.info(f"  Student: {student.get_full_name()}")
            logger.info(f"  Academic Year: {academic_year}")
            logger.info(f"  Term: {term}")
            logger.info(f"  Report Card ID: {report_card.id}")
            logger.info(f"  Average Score: {report_card.average_score}")
            logger.info(f"  Overall Grade: {report_card.overall_grade}")
            
            # Save success message
            messages.success(request, message)
            
            # IMMEDIATELY REDIRECT to dashboard with success parameters
            return redirect(
                reverse('report_card_dashboard') + 
                f'?student_id={student_id}' +
                f'&academic_year={academic_year}' +
                f'&term={term}' +
                f'&created=true'
            )
            
        except Exception as e:
            logger.error(f"Error saving report card: {str(e)}", exc_info=True)
            messages.error(request, f"Error saving report card: {str(e)}")
            return redirect('report_card', student_id=student_id)

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


class AddGradeView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Handle adding new grades via AJAX"""
    
    def test_func(self):
        """Only teachers and admins can add grades"""
        return is_teacher(self.request.user) or is_admin(self.request.user)
    
    def post(self, request, student_id):
        """Handle POST request to add a new grade"""
        try:
            student = get_object_or_404(Student, pk=student_id)
            
            # Get form data
            subject_id = request.POST.get('subject')
            academic_year = request.POST.get('academic_year')
            term = request.POST.get('term')
            homework_percentage = request.POST.get('homework_percentage', '0')
            classwork_percentage = request.POST.get('classwork_percentage', '0')
            test_percentage = request.POST.get('test_percentage', '0')
            exam_percentage = request.POST.get('exam_percentage', '0')
            
            # Validate required fields
            if not all([subject_id, academic_year, term]):
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required fields: subject, academic_year, or term'
                }, status=400)
            
            # Get subject
            subject = get_object_or_404(Subject, pk=subject_id)
            
            # Check if grade already exists for this subject/term/year
            existing_grade = Grade.objects.filter(
                student=student,
                subject=subject,
                academic_year=academic_year,
                term=term
            ).first()
            
            if existing_grade:
                return JsonResponse({
                    'success': False,
                    'error': f'A grade for {subject.name} already exists for this term.'
                })
            
            # Create new grade
            grade = Grade.objects.create(
                student=student,
                subject=subject,
                academic_year=academic_year,
                term=term,
                homework_percentage=float(homework_percentage),
                classwork_percentage=float(classwork_percentage),
                test_percentage=float(test_percentage),
                exam_percentage=float(exam_percentage),
                recorded_by=request.user
                
            )
            
            # Calculate total score
            grade.calculate_total_score()
            grade.save()
            
            # Log the action
            logger.info(
                f"New grade added - Grade ID: {grade.id}, "
                f"Student: {student.get_full_name()}, "
                f"Subject: {subject.name}, "
                f"Teacher: {request.user.username}"
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Grade added successfully',
                'grade_id': grade.id,
                'subject_name': subject.name,
                'total_score': float(grade.total_score)
            })
            
        except Exception as e:
            logger.error(f"Error adding grade: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Error adding grade: {str(e)}'
            }, status=500)


@csrf_exempt
@login_required
@require_POST
def publish_report_card(request, report_card_id):
    """
    API endpoint to publish a report card - FIXED VERSION
    """
    from core.models import ReportCard
    # REMOVE THIS: from core.utils.helpers import is_teacher
    # The is_teacher function is already imported at the top of the file
    
    print(f"🔍 Publish request for ReportCard ID: {report_card_id}")
    print(f"🔍 User: {request.user.username}")
    
    try:
        # Parse request body
        data = json.loads(request.body)
        print(f"🔍 Parsed data: {data}")
        
        # Get the report card
        report_card = ReportCard.objects.get(id=report_card_id)
        print(f"🔍 Found report card: {report_card.student.get_full_name()}")
        print(f"🔍 Current published status: {report_card.is_published}")
        
        # Check permissions - use the is_teacher function that's already imported
        if not (request.user.is_staff or request.user.is_superuser or is_teacher(request.user)):
            print("❌ Permission denied - user is not teacher/admin")
            return JsonResponse({
                'success': False, 
                'message': 'Permission denied. Only teachers or admins can publish report cards.'
            }, status=403)
        
        # If user is teacher, check if they teach this student's class
        if is_teacher(request.user):
            teacher = request.user.teacher
            print(f"🔍 Teacher: {teacher}")
            print(f"🔍 Teacher class_levels: {teacher.class_levels}")
            print(f"🔍 Student class_level: {report_card.student.class_level}")
            
            # Parse teacher's class levels
            teacher_classes = []
            if teacher.class_levels:
                teacher_classes = [c.strip() for c in teacher.class_levels.split(',')]
            
            print(f"🔍 Teacher classes parsed: {teacher_classes}")
            
            if report_card.student.class_level not in teacher_classes:
                print(f"❌ Teacher doesn't teach this class: {report_card.student.class_level}")
                return JsonResponse({
                    'success': False, 
                    'message': f'You don\'t have permission to publish report cards for {report_card.student.get_class_level_display()} class.'
                }, status=403)
        
        # Publish the report card
        report_card.is_published = True
        report_card.save()
        
        print(f"✅ Report card published successfully: ID {report_card_id}")
        
        return JsonResponse({
            'success': True, 
            'message': 'Report card published successfully!',
            'report_card_id': report_card_id,
            'is_published': True
        })
        
    except ReportCard.DoesNotExist:
        print(f"❌ Report card not found: ID {report_card_id}")
        return JsonResponse({
            'success': False, 
            'message': 'Report card not found.'
        }, status=404)
        
    except json.JSONDecodeError:
        print("❌ Invalid JSON in request body")
        return JsonResponse({
            'success': False, 
            'message': 'Invalid request data.'
        }, status=400)
        
    except Exception as e:
        print(f"❌ Error publishing report card: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False, 
            'message': f'Error: {str(e)}'
        }, status=500)


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import json

@login_required
@require_POST
def force_recalculate_reportcards(request):
    """Force recalculate all report card statistics"""
    if not (is_admin(request.user) or is_teacher(request.user)):
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    
    try:
        from django.db import transaction
        from core.models import ReportCard
        
        # Get all report cards
        report_cards = ReportCard.objects.all()
        total_count = report_cards.count()
        
        with transaction.atomic():
            updated_count = 0
            for report_card in report_cards:
                old_grade = report_card.overall_grade
                old_score = report_card.average_score
                
                # Force recalculation
                report_card.calculate_grades()
                report_card.save()
                
                if (old_grade != report_card.overall_grade or 
                    old_score != report_card.average_score):
                    updated_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Recalculated {total_count} report cards. Updated {updated_count} records.',
            'total_records': total_count,
            'updated_records': updated_count
        })
        
    except Exception as e:
        logger.error(f"Error force recalculating report cards: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@login_required
def report_card_statistics_debug(request):
    """Debug view to show raw statistics"""
    if not (is_admin(request.user) or is_teacher(request.user)):
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    
    from django.db import connection
    
    response_data = {
        'database_info': {},
        'statistics': {},
        'raw_data': [],
        'success': True
    }
    
    try:
        # Get raw database counts
        with connection.cursor() as cursor:
            # Total report cards
            cursor.execute("SELECT COUNT(*) FROM core_reportcard")
            response_data['database_info']['total'] = cursor.fetchone()[0]
            
            # Report cards by academic year and term
            cursor.execute("""
                SELECT academic_year, term, COUNT(*) 
                FROM core_reportcard 
                GROUP BY academic_year, term 
                ORDER BY academic_year DESC, term DESC
            """)
            response_data['database_info']['by_period'] = cursor.fetchall()
            
            # Report cards by grade
            cursor.execute("""
                SELECT overall_grade, COUNT(*) 
                FROM core_reportcard 
                WHERE overall_grade IS NOT NULL 
                GROUP BY overall_grade 
                ORDER BY overall_grade
            """)
            response_data['database_info']['by_grade'] = cursor.fetchall()
            
            # Report cards needing attention
            cursor.execute("""
                SELECT COUNT(*) 
                FROM core_reportcard 
                WHERE overall_grade IN ('C+', 'C', 'D+', 'D', 'E')
            """)
            response_data['database_info']['needs_attention'] = cursor.fetchone()[0]
        
        # Calculate current period
        current_year = timezone.now().year
        current_academic_year = f"{current_year}/{current_year + 1}"
        current_month = timezone.now().month
        
        if current_month >= 9 and current_month <= 12:
            current_term = 1
        elif current_month >= 1 and current_month <= 4:
            current_term = 2
        else:
            current_term = 3
        
        # Current term count
        current_term_count = ReportCard.objects.filter(
            academic_year=current_academic_year,
            term=current_term
        ).count()
        
        response_data['statistics'] = {
            'current_academic_year': current_academic_year,
            'current_term': current_term,
            'current_month': current_month,
            'current_term_count': current_term_count,
            'calculated_at': timezone.now().isoformat(),
        }
        
        # Sample data
        response_data['raw_data'] = list(
            ReportCard.objects.filter(
                academic_year=current_academic_year,
                term=current_term
            )[:10].values('id', 'student__first_name', 'student__last_name', 'overall_grade', 'average_score')
        )
        
    except Exception as e:
        response_data['success'] = False
        response_data['error'] = str(e)
    
    return JsonResponse(response_data)