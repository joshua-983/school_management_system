from django.db.models import Avg, Count, Q  # ADDED Q import
from django.views.generic import TemplateView, CreateView, View
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from django.http import HttpResponse, Http404, JsonResponse
import re
import logging
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from datetime import datetime

from ..models import (
    ReportCard, Student, Subject, Grade, StudentAttendance, AcademicTerm, 
    ClassAssignment, SchoolConfiguration
)
from .base_views import is_student, is_teacher, is_admin
from ..forms import ReportCardForm, ReportCardFilterForm

logger = logging.getLogger(__name__)

class ReportCardDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/academics/report_cards/report_card_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get report cards based on user role
        if is_student(self.request.user):
            student = self.request.user.student
            report_cards = ReportCard.objects.filter(
                student=student
            ).select_related('student').order_by('-academic_year', '-term')
        
        elif is_teacher(self.request.user):
            # Get classes this teacher teaches
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            
            # Get report cards for students in those classes
            report_cards = ReportCard.objects.filter(
                student__class_level__in=teacher_classes
            ).select_related('student').order_by('-academic_year', '-term')
            
            # Add teacher's students for quick view modal
            context['teacher_students'] = Student.objects.filter(
                class_level__in=teacher_classes,
                is_active=True
            ).order_by('class_level', 'last_name', 'first_name')
        
        else:
            # Admin or other users see all report cards
            report_cards = ReportCard.objects.all().select_related('student').order_by('-academic_year', '-term')
            
            # Add all students for quick view modal
            context['all_students'] = Student.objects.filter(
                is_active=True
            ).order_by('class_level', 'last_name', 'first_name')
        
        # Apply filters from GET parameters
        academic_year = self.request.GET.get('academic_year')
        term = self.request.GET.get('term')
        class_level = self.request.GET.get('class_level')
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        grade_range = self.request.GET.get('grade_range')
        sort_by = self.request.GET.get('sort_by')
        
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
            term=2  # You can make this dynamic based on current date
        ).count()
        
        # Pagination
        paginator = Paginator(report_cards, 20)  # Show 20 report cards per page
        page = self.request.GET.get('page')
        try:
            report_cards_page = paginator.page(page)
        except PageNotAnInteger:
            report_cards_page = paginator.page(1)
        except EmptyPage:
            report_cards_page = paginator.page(paginator.num_pages)
        
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
        })
        
        return context


class QuickViewReportCardView(LoginRequiredMixin, View):
    """Quick view report card - redirects to the detailed view"""
    
    def get(self, request):
        student_id = request.GET.get('student_id')
        academic_year = request.GET.get('academic_year')
        term = request.GET.get('term')
        
        if not all([student_id, academic_year, term]):
            messages.error(request, 'Please select student, academic year, and term')
            return redirect('report_card_dashboard')
        
        try:
            student = Student.objects.get(pk=student_id)
            
            # Check permissions
            if is_student(request.user) and request.user.student != student:
                raise PermissionDenied("You can only view your own report cards")
            elif is_teacher(request.user):
                if not ClassAssignment.objects.filter(
                    class_level=student.class_level,
                    teacher=request.user.teacher
                ).exists():
                    raise PermissionDenied("You can only view report cards for your assigned classes")
            
            # Try to find existing report card
            report_card = ReportCard.objects.filter(
                student=student,
                academic_year=academic_year,
                term=term
            ).first()
            
            if report_card:
                # Redirect to existing report card detail view
                return redirect('report_card_detail', student_id=student_id, report_card_id=report_card.id)
            else:
                # Redirect to report card view with parameters
                return redirect(f'{reverse("report_card", kwargs={"student_id": student_id})}?academic_year={academic_year}&term={term}')
                
        except Student.DoesNotExist:
            messages.error(request, 'Student not found')
            return redirect('report_card_dashboard')
        except Exception as e:
            logger.error(f"Quick view error: {str(e)}")
            messages.error(request, f'Error viewing report card: {str(e)}')
            return redirect('report_card_dashboard')


class QuickViewReportCardPDFView(LoginRequiredMixin, View):
    """Quick view report card as PDF download"""
    
    def get(self, request):
        student_id = request.GET.get('student_id')
        academic_year = request.GET.get('academic_year')
        term = request.GET.get('term')
        
        if not all([student_id, academic_year, term]):
            messages.error(request, 'Please select student, academic year, and term')
            return redirect('report_card_dashboard')
        
        try:
            student = Student.objects.get(pk=student_id)
            
            # Check permissions
            if is_student(request.user) and request.user.student != student:
                raise PermissionDenied("You can only view your own report cards")
            elif is_teacher(request.user):
                if not ClassAssignment.objects.filter(
                    class_level=student.class_level,
                    teacher=request.user.teacher
                ).exists():
                    raise PermissionDenied("You can only view report cards for your assigned classes")
            
            # Try to find existing report card
            report_card = ReportCard.objects.filter(
                student=student,
                academic_year=academic_year,
                term=term
            ).first()
            
            if report_card:
                # Generate PDF for existing report card
                return redirect('report_card_pdf_detail', student_id=student_id, report_card_id=report_card.id)
            else:
                # Generate PDF directly from grades
                return redirect(f'{reverse("report_card_pdf", kwargs={"student_id": student_id})}?academic_year={academic_year}&term={term}')
                
        except Student.DoesNotExist:
            messages.error(request, 'Student not found')
            return redirect('report_card_dashboard')
        except Exception as e:
            logger.error(f"Quick view PDF error: {str(e)}")
            messages.error(request, f'Error generating PDF: {str(e)}')
            return redirect('report_card_dashboard')


class CreateReportCardView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ReportCard
    form_class = ReportCardForm
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
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Set the created_by field
        form.instance.created_by = self.request.user
        
        # Calculate initial grades
        form.instance.calculate_grades()
        
        response = super().form_valid(form)
        messages.success(self.request, f'Report card for {form.instance.student.get_full_name()} created successfully!')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Report Card'
        return context


class ReportCardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Complete ReportCardView with all new features including attendance and additional info
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
        
        if is_admin(self.request.user):
            return True
        
        if is_student(self.request.user):
            return self.request.user.student == student
        
        if is_teacher(self.request.user):
            return ClassAssignment.objects.filter(
                class_level=student.class_level,
                teacher=self.request.user.teacher
            ).exists()
        
        return False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("You don't have permission to view this report card")
        return super().handle_no_permission()
    
    def get(self, request, student_id, report_card_id=None):
        try:
            student_id = int(student_id)
        except (ValueError, TypeError):
            raise Http404("Invalid student ID format")
        
        student = get_object_or_404(Student, pk=student_id)
        report_card = self._get_report_card(report_card_id, student)
        
        # Get filtered grades and aggregate data
        grades, aggregates = self._get_grade_data(request, student, report_card)
        
        # Get attendance data
        attendance_data = self._get_attendance_data(student, aggregates)
        
        # Get additional information
        additional_info = self._get_additional_info(student, aggregates)
        
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
        }

        return render(request, 'core/academics/report_cards/report_card.html', context)

    def _get_report_card(self, report_card_id, student):
        """Get specific report card or return None"""
        if report_card_id:
            try:
                return get_object_or_404(ReportCard, pk=report_card_id, student=student)
            except (ValueError, TypeError):
                raise Http404("Invalid report card ID")
        return None
    
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
        
        grades = grades.order_by('subject__name')
        
        # Calculate aggregates
        aggregates = grades.aggregate(
            avg_score=Avg('total_score')
        )
        
        average_score = aggregates['avg_score']
        if average_score is None:
            average_score = 0.0
        
        # Calculate overall grade
        try:
            overall_grade = self._calculate_letter_grade(average_score)
        except (AttributeError, ValueError):
            overall_grade = self._calculate_fallback_grade(average_score)
        
        return grades, {
            'average_score': round(float(average_score), 2),
            'overall_grade': overall_grade,
            'academic_year': academic_year,
            'term': term,
        }
    
    def _get_attendance_data(self, student, aggregates):
        """Get attendance data for the student"""
        try:
            # Use the term object instead of academic_year and term fields
            academic_term = AcademicTerm.objects.filter(
                academic_year=aggregates['academic_year'],
                term=aggregates['term']
            ).first()
            
            if not academic_term:
                return {
                    'total_days': 0,
                    'present_days': 0,
                    'absence_count': 0,
                    'attendance_rate': 0,
                }
            
            attendance_records = StudentAttendance.objects.filter(
                student=student,
                term=academic_term  # Use the term object
            )
            
            total_days = attendance_records.count()
            if total_days == 0:
                return {
                    'total_days': 0,
                    'present_days': 0,
                    'absence_count': 0,
                    'attendance_rate': 0,
                }
            
            present_days = attendance_records.filter(
                Q(status='present') | Q(status='late') | Q(status='excused')
            ).count()
            
            absence_count = attendance_records.filter(status='absent').count()
            attendance_rate = round((present_days / total_days) * 100, 1)
            
            return {
                'total_days': total_days,
                'present_days': present_days,
                'absence_count': absence_count,
                'attendance_rate': attendance_rate,
            }
        except Exception as e:
            logger.error(f"Error getting attendance data for student {student.id}: {str(e)}")
            return {
                'total_days': 0,
                'present_days': 0,
                'absence_count': 0,
                'attendance_rate': 0,
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
            
            # Calculate position in class
            position_in_class = self._calculate_class_position(student, aggregates)
            
            return {
                'vacation_date': vacation_date.strftime('%B %d, %Y') if vacation_date else "To be announced",
                'reopening_date': reopening_date.strftime('%B %d, %Y') if reopening_date else "To be announced",
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
    
    def _calculate_class_position(self, student, aggregates):
        """Calculate student's position in class based on average scores"""
        try:
            # Get all active students in the same class
            classmates = Student.objects.filter(
                class_level=student.class_level,
                is_active=True
            ).exclude(pk=student.pk)  # Exclude current student initially
            
            # Calculate average scores for all classmates including current student
            student_scores = []
            
            # Add current student first
            current_student_avg = aggregates['average_score']
            student_scores.append({
                'student': student,
                'average_score': current_student_avg
            })
            
            # Add classmates
            for classmate in classmates:
                grades = Grade.objects.filter(
                    student=classmate,
                    academic_year=aggregates['academic_year'],
                    term=aggregates['term']
                )
                
                if grades.exists():
                    avg_score = grades.aggregate(avg=Avg('total_score'))['avg'] or 0
                    student_scores.append({
                        'student': classmate,
                        'average_score': float(avg_score)
                    })
            
            # Sort by average score descending
            student_scores.sort(key=lambda x: x['average_score'], reverse=True)
            
            # Find current student's position
            for index, score_data in enumerate(student_scores, 1):
                if score_data['student'] == student:
                    total_students = len(student_scores)
                    
                    # Return position with ordinal suffix
                    if index == 1:
                        return "1st"
                    elif index == 2:
                        return "2nd" 
                    elif index == 3:
                        return "3rd"
                    else:
                        return f"{index}th"
            
            return "Not ranked"
            
        except Exception as e:
            logger.error(f"Error calculating class position for student {student.id}: {str(e)}")
            return "Not ranked"
    
    def _calculate_letter_grade(self, score):
        """Calculate letter grade based on score"""
        try:
            score = float(score)
            if score >= 90: return 'A+'
            elif score >= 80: return 'A'
            elif score >= 70: return 'B+'
            elif score >= 60: return 'B'
            elif score >= 50: return 'C+'
            elif score >= 40: return 'C'
            elif score >= 30: return 'D+'
            elif score >= 20: return 'D'
            else: return 'E'
        except (ValueError, TypeError):
            return 'N/A'
    
    def _calculate_fallback_grade(self, score):
        """Fallback grade calculation if main method fails"""
        return self._calculate_letter_grade(score)


class ReportCardPDFView(LoginRequiredMixin, View):
    """
    Enhanced PDF view with all new information included
    """
    
    def get(self, request, student_id, report_card_id=None):
        student = get_object_or_404(Student, pk=student_id)
        
        # Check permissions
        if is_student(request.user) and request.user.student != student:
            raise PermissionDenied("You can only view your own report cards")
        elif is_teacher(request.user):
            if not ClassAssignment.objects.filter(
                class_level=student.class_level,
                teacher=request.user.teacher
            ).exists():
                raise PermissionDenied("You can only view report cards for your assigned classes")
        
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
        
        grades = grades.order_by('subject__name')
        
        # Calculate aggregates
        aggregates = grades.aggregate(avg_score=Avg('total_score'))
        average_score = aggregates['avg_score'] or 0.0
        overall_grade = self._calculate_letter_grade(average_score)
        
        # Get attendance data
        attendance_data = self._get_attendance_data(student, academic_year, term)
        
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
    
    def _get_attendance_data(self, student, academic_year, term):
        """Get attendance data for PDF"""
        try:
            # Use the term object
            academic_term = AcademicTerm.objects.filter(
                academic_year=academic_year,
                term=term
            ).first()
            
            if not academic_term:
                return {
                    'total_days': 0,
                    'present_days': 0,
                    'absence_count': 0,
                    'attendance_rate': 0,
                }
            
            attendance_records = StudentAttendance.objects.filter(
                student=student,
                term=academic_term  # Use the term object
            )
            
            total_days = attendance_records.count()
            if total_days == 0:
                return {
                    'total_days': 0,
                    'present_days': 0,
                    'absence_count': 0,
                    'attendance_rate': 0,
                }
            
            present_days = attendance_records.filter(
                Q(status='present') | Q(status='late') | Q(status='excused')
            ).count()
            
            absence_count = attendance_records.filter(status='absent').count()
            attendance_rate = round((present_days / total_days) * 100, 1)
            
            return {
                'total_days': total_days,
                'present_days': present_days,
                'absence_count': absence_count,
                'attendance_rate': attendance_rate,
            }
        except Exception as e:
            logger.error(f"Error getting attendance data for PDF: {str(e)}")
            return {
                'total_days': 0,
                'present_days': 0,
                'absence_count': 0,
                'attendance_rate': 0,
            }
    
    def _get_additional_info(self, student, academic_year, term):
        """Get additional information for PDF"""
        try:
            academic_term = AcademicTerm.objects.filter(
                academic_year=academic_year,
                term=term
            ).first()
            
            vacation_date = academic_term.end_date if academic_term else None
            reopening_date = self._calculate_reopening_date(academic_term) if academic_term else None
            
            # Simplified class position calculation for PDF
            position_in_class = "Calculated"  # You can implement the full logic here if needed
            
            return {
                'vacation_date': vacation_date.strftime('%B %d, %Y') if vacation_date else "To be announced",
                'reopening_date': reopening_date.strftime('%B %d, %Y') if reopening_date else "To be announced",
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
    
    def _calculate_letter_grade(self, score):
        """Calculate letter grade"""
        try:
            score = float(score)
            if score >= 90: return 'A+'
            elif score >= 80: return 'A'
            elif score >= 70: return 'B+'
            elif score >= 60: return 'B'
            elif score >= 50: return 'C+'
            elif score >= 40: return 'C'
            elif score >= 30: return 'D+'
            elif score >= 20: return 'D'
            else: return 'E'
        except (ValueError, TypeError):
            return 'N/A'
    
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
            ['Class Level:', student.get_class_level_display()],
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
        ]
        
        summary_table = Table(summary_data, colWidths=[100, 80])
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
            ('SPAN', (0, 1), (0, 1)),  # Make signature lines span cells if needed
        ]))
        
        elements.append(signature_table)


class SaveReportCardView(LoginRequiredMixin, View):
    def post(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        
        if not is_teacher(request.user):
            raise PermissionDenied("Only teachers can save report cards")
        
        academic_year = request.POST.get('academic_year')
        term = request.POST.get('term')
        
        # Validate academic year format (YYYY/YYYY)
        if not re.match(r'^\d{4}/\d{4}$', academic_year):
            messages.error(request, 'Invalid academic year format. Use YYYY/YYYY format.')
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
        
        if created:
            messages.success(request, 'Report card created successfully!')
        else:
            messages.info(request, 'Report card already exists.')
        
        return redirect('report_card_detail', student_id=student_id, report_card_id=report_card.id)