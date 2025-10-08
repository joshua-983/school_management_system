from django.db.models import Avg
from django.views.generic import TemplateView, CreateView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from ..models import ReportCard, Student, Subject, Grade
from .base_views import is_student, is_teacher, is_admin
from ..forms import ReportCardForm, ReportCardFilterForm  # Add ReportCardFilterForm here
from django.shortcuts import render, redirect, get_object_or_404

from ..models import ReportCard, Student, Subject, Grade, ClassAssignment
from .base_views import is_student, is_teacher, is_admin
from ..forms import ReportCardForm, ReportCardFilterForm
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count
from django.utils import timezone




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
        else:
            # Admin or other users see all report cards
            report_cards = ReportCard.objects.all().select_related('student').order_by('-academic_year', '-term')
        
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


class CreateReportCardView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ReportCard
    form_class = ReportCardForm
    template_name = 'core/academics/report_cards/create_report_card.html'  # Fixed path
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

class ReportCardView(LoginRequiredMixin, View):
    def get(self, request, student_id, report_card_id=None):
        student = get_object_or_404(Student, pk=student_id)
        
        # Check permissions more efficiently
        if not self._has_permission(request, student):
            raise PermissionDenied
        
        # Get report card if specified
        report_card = self._get_report_card(report_card_id, student)
        
        # Get filtered grades and aggregate data
        grades, aggregates = self._get_grade_data(request, student)
        
        context = {
            'student': student,
            'grades': grades,
            'average_score': aggregates['average_score'],
            'overall_grade': aggregates['overall_grade'],
            'academic_year': aggregates['academic_year'],
            'term': aggregates['term'],
            'report_card': report_card,
            'form': ReportCardFilterForm(request.GET),
        }

        return render(request, 'core/academics/report_cards/report_card.html', context)

    def _has_permission(self, request, student):
        """Check if user has permission to view this report card"""
        if is_admin(request.user):
            return True
        if is_student(request.user) and request.user.student == student:
            return True
        if is_teacher(request.user):
            return ClassAssignment.objects.filter(
                class_level=student.class_level,
                teacher=request.user.teacher
            ).exists()
        return False
    
    def _get_report_card(self, report_card_id, student):
        """Get specific report card or return None"""
        if report_card_id:
            return get_object_or_404(ReportCard, pk=report_card_id, student=student)
        return None
    
    def _get_grade_data(self, request, student):
        """Get filtered grades and calculate aggregates with proper error handling"""
        grades = Grade.objects.filter(student=student)
        
        # Apply filters from GET parameters
        form = ReportCardFilterForm(request.GET)
        if form.is_valid():
            if form.cleaned_data.get('academic_year'):
                grades = grades.filter(academic_year=form.cleaned_data['academic_year'])
            if form.cleaned_data.get('term'):
                grades = grades.filter(term=form.cleaned_data['term'])
        
        grades = grades.order_by('subject__name')
        
        # Get academic year and term from grades if no report card
        academic_year = grades[0].academic_year if grades.exists() else "2024/2025"
        term = grades[0].term if grades.exists() else 1
        
        # Calculate average safely
        aggregates = grades.aggregate(
            avg_score=Avg('total_score')
        )
        
        # Handle average score calculation
        average_score = aggregates['avg_score']
        if average_score is None:
            average_score = 0.0
        
        # Safely calculate grade with fallback
        try:
            overall_grade = Grade.calculate_grade(average_score)
        except (AttributeError, ValueError):
            overall_grade = self._calculate_fallback_grade(average_score)
        
        return grades, {
            'average_score': round(float(average_score), 2),
            'overall_grade': overall_grade,
            'academic_year': academic_year,
            'term': term,
        }
    
    def _calculate_fallback_grade(self, score):
        """Fallback grade calculation if Grade model method isn't available"""
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

class ReportCardPDFView(LoginRequiredMixin, View):
    def get(self, request, student_id, report_card_id=None):
        student = get_object_or_404(Student, pk=student_id)
        
        # Check permissions
        if is_student(request.user) and request.user.student != student:
            raise PermissionDenied
        elif is_teacher(request.user):
            if not ClassAssignment.objects.filter(
                class_level=student.class_level,
                teacher=request.user.teacher
            ).exists():
                raise PermissionDenied
        
        # Get grades with optional filtering
        grades = Grade.objects.filter(student=student)
        
        # Apply filters if report_card_id is provided
        if report_card_id:
            report_card = get_object_or_404(ReportCard, pk=report_card_id, student=student)
            grades = grades.filter(
                academic_year=report_card.academic_year,
                term=report_card.term
            )
        else:
            # Apply filters from GET parameters
            form = ReportCardFilterForm(request.GET)
            if form.is_valid():
                academic_year = form.cleaned_data.get('academic_year')
                term = form.cleaned_data.get('term')
                
                if academic_year:
                    grades = grades.filter(academic_year=academic_year)
                if term:
                    grades = grades.filter(term=term)
        
        grades = grades.order_by('subject')
        
        # Create PDF
        response = HttpResponse(content_type='application/pdf')
        filename = f"Report_Card_{student.student_id}"
        if report_card_id:
            filename += f"_{report_card.academic_year}_Term{report_card.term}"
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        
        p = canvas.Canvas(response, pagesize=letter)
        width, height = letter
        
        # PDF content creation (similar to your original implementation)
        # ... [include all your PDF generation code here] ...
        
        p.showPage()
        p.save()
        return response

class SaveReportCardView(LoginRequiredMixin, View):
    def post(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        
        if not is_teacher(request.user):
            raise PermissionDenied
        
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