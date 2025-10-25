from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.db.models import Count, Q
from datetime import datetime, date
from urllib.parse import urlencode

from .base_views import *
from ..models import AcademicTerm, AttendancePeriod, StudentAttendance, Student, ClassAssignment
# Attendance Period Views
from ..models import AcademicTerm, AttendancePeriod, StudentAttendance, Student, ClassAssignment, CLASS_LEVEL_CHOICES
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from .base_views import is_admin, is_teacher

class AttendanceBaseView(LoginRequiredMixin, UserPassesTestMixin):
    """Base view for attendance-related views with common permissions"""
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)


class GhanaEducationAttendanceMixin:
    """Mixin for Ghana Education Service specific attendance functionality"""
    
    def get_ghana_academic_calendar(self):
        """Get current Ghana academic calendar structure"""
        current_year = datetime.now().year
        next_year = current_year + 1
        
        # Ghana Education Service Standard Calendar (adjust as needed)
        ghana_calendar = {
            'academic_year': f"{current_year}/{next_year}",
            'terms': {
                1: {
                    'name': 'Term 1',
                    'start_date': date(current_year, 9, 2),  # Early September
                    'end_date': date(current_year, 12, 18),  # Mid-December
                    'mid_term_break': date(current_year, 10, 16),  # Approximate
                },
                2: {
                    'name': 'Term 2', 
                    'start_date': date(next_year, 1, 8),     # Early January
                    'end_date': date(next_year, 4, 1),       # Early April
                    'mid_term_break': date(next_year, 2, 15),  # Approximate
                },
                3: {
                    'name': 'Term 3',
                    'start_date': date(next_year, 4, 21),    # Late April
                    'end_date': date(next_year, 7, 23),      # Late July
                    'mid_term_break': date(next_year, 6, 1),   # Approximate
                }
            }
        }
        return ghana_calendar
    
    def is_ghana_school_day(self, check_date):
        """
        Check if date is a valid school day in Ghana
        - Monday to Friday are school days
        - Exclude public holidays (basic implementation)
        """
        # Monday = 0, Friday = 4, Saturday = 5, Sunday = 6
        if check_date.weekday() >= 5:  # Weekend
            return False
        
        # Basic Ghana public holidays (you can expand this)
        ghana_holidays = [
            date(check_date.year, 1, 1),   # New Year
            date(check_date.year, 3, 6),   # Independence Day
            date(check_date.year, 5, 1),   # Workers Day
            date(check_date.year, 7, 1),   # Republic Day
            date(check_date.year, 12, 25), # Christmas
            date(check_date.year, 12, 26), # Boxing Day
        ]
        
        return check_date not in ghana_holidays
    
    def calculate_ges_attendance_rate(self, student, term):
        """Calculate attendance rate following GES requirements (80% minimum)"""
        total_school_days = self._get_total_school_days(term)
        if total_school_days == 0:
            return 0
        
        present_days = StudentAttendance.objects.filter(
            student=student,
            term=term,
            status__in=['present', 'late', 'excused']  # GES counts late and excused as present
        ).count()
        
        attendance_rate = (present_days / total_school_days) * 100
        return round(attendance_rate, 1)
    
    def _get_total_school_days(self, term):
        """Calculate total school days in a term (basic implementation)"""
        from datetime import timedelta
        
        current_date = term.start_date
        school_days = 0
        
        while current_date <= term.end_date:
            if self.is_ghana_school_day(current_date):
                school_days += 1
            current_date += timedelta(days=1)
        
        return school_days


class AttendanceDashboardView(AttendanceBaseView, GhanaEducationAttendanceMixin, TemplateView):
    """Dashboard view showing attendance overview and statistics - Ghana Education System"""
    template_name = 'core/academics/attendance_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        # Get terms and periods
        terms = AcademicTerm.objects.all().order_by('-start_date')
        active_term = terms.filter(is_active=True).first()
        periods = AttendancePeriod.objects.filter(term=active_term).order_by('-start_date') if active_term else []
        
        # Get filtered attendance data
        today_attendance = self._get_filtered_attendance(today, active_term)
        
        # Prepare statistics with Ghana education context
        stats = self._calculate_attendance_stats(today_attendance, active_term)
        class_stats = self._calculate_class_stats(today_attendance)
        
        # Ghana Education specific data
        ghana_context = self._get_ghana_education_context(active_term)
        
        context.update({
            'today': today,
            'today_attendance': today_attendance,
            'terms': terms,
            'periods': periods,
            'class_levels': CLASS_LEVEL_CHOICES,
            'status_choices': StudentAttendance.STATUS_CHOICES,
            'stats': stats,
            'class_stats': class_stats,
            'active_term': active_term,
            **ghana_context,  # Add Ghana education context
        })
        return context

    def _get_filtered_attendance(self, date, active_term):
        """Filter attendance records with optimized queries - FIXED VERSION"""
        queryset = StudentAttendance.objects.filter(
            date=date
        ).select_related('student', 'term', 'period').order_by(
            'student__class_level',
            'student__last_name',
            'student__first_name'
        )
        
        # Filter by active term if available
        if active_term:
            queryset = queryset.filter(term=active_term)
        
        if is_teacher(self.request.user):
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            queryset = queryset.filter(student__class_level__in=teacher_classes)
        
        # FIXED: Pre-calculate attendance rates for all students in one query
        if active_term and queryset.exists():
            # Get all student IDs from today's attendance
            student_ids = list(queryset.values_list('student_id', flat=True))
            
            if student_ids:
                # Calculate attendance rates for these students in bulk using Django ORM
                from django.db.models import Count, Case, When, IntegerField, FloatField
                from django.db.models.functions import Cast
                
                # Get all attendance records for these students in the active term
                term_attendance = StudentAttendance.objects.filter(
                    student_id__in=student_ids,
                    term=active_term
                )
                
                # Calculate statistics for each student
                attendance_stats = term_attendance.values('student_id').annotate(
                    total_days=Count('id'),
                    present_days=Count(
                        Case(
                            When(status__in=['present', 'late', 'excused'], then=1),
                            output_field=IntegerField()
                        )
                    )
                ).annotate(
                    attendance_rate=Case(
                        When(total_days=0, then=0.0),
                        default=Cast('present_days', FloatField()) / Cast('total_days', FloatField()) * 100.0,
                        output_field=FloatField()
                    )
                )
                
                # Create a dictionary for quick lookup
                attendance_dict = {}
                for stat in attendance_stats:
                    student_id = stat['student_id']
                    attendance_rate = round(stat['attendance_rate'], 1)
                    attendance_dict[student_id] = attendance_rate
                
                # Add attendance rates to each record
                for record in queryset:
                    record.term_attendance_rate = attendance_dict.get(record.student.id, 0.0)
                    # Also add absence count
                    record.absence_count = term_attendance.filter(
                        student=record.student,
                        status='absent'
                    ).count()
            else:
                # If no student IDs, set default values
                for record in queryset:
                    record.term_attendance_rate = 0.0
                    record.absence_count = 0
        else:
            # Set default values if no active term
            for record in queryset:
                record.term_attendance_rate = 0.0
                record.absence_count = 0
        
        return queryset

    def _get_ghana_education_context(self, active_term):
        """Get Ghana Education Service specific context data"""
        context = {}
        
        if active_term:
            # Calculate GES compliance statistics
            context['ges_attendance_rate'] = self._calculate_school_ges_attendance_rate(active_term)
            context['low_attendance_students'] = self._get_low_attendance_students(active_term)
            context['term_progress'] = self._calculate_term_progress(active_term)
        
        context['ghana_calendar'] = self.get_ghana_academic_calendar()
        context['is_school_day'] = self.is_ghana_school_day(timezone.now().date())
        
        return context

    def _calculate_school_ges_attendance_rate(self, term):
        """Calculate overall school attendance rate for GES reporting"""
        total_students = Student.objects.filter(is_active=True).count()
        if total_students == 0:
            return 0
        
        total_attendance_rate = 0
        students = Student.objects.filter(is_active=True)
        
        for student in students:
            total_attendance_rate += self.calculate_ges_attendance_rate(student, term)
        
        return round(total_attendance_rate / total_students, 1) if total_students > 0 else 0

    def _get_low_attendance_students(self, term, threshold=80):
        """Identify students with attendance below GES requirement (80%)"""
        low_attendance = []
        students = Student.objects.filter(is_active=True)
        
        for student in students:
            attendance_rate = self.calculate_ges_attendance_rate(student, term)
            if attendance_rate < threshold:
                low_attendance.append({
                    'student': student,
                    'attendance_rate': attendance_rate,
                    'class_level': student.get_class_level_display()
                })
        
        return low_attendance[:10]  # Return top 10 for dashboard

    def _calculate_term_progress(self, term):
        """Calculate how far we are into the current term"""
        today = timezone.now().date()
        total_days = (term.end_date - term.start_date).days
        days_passed = (today - term.start_date).days
        
        if total_days > 0 and days_passed >= 0:
            progress = min(100, max(0, (days_passed / total_days) * 100))
            return round(progress, 1)
        return 0

    def _calculate_attendance_stats(self, attendance, active_term):
        """Calculate and return attendance statistics with Ghana context"""
        # Get total students based on user role
        if is_teacher(self.request.user):
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            total_students = Student.objects.filter(
                class_level__in=teacher_classes, 
                is_active=True
            ).count()
        else:
            total_students = Student.objects.filter(is_active=True).count()
            
        present_today = attendance.filter(status='present').count()
        absent_today = attendance.filter(status='absent').count()
        late_today = attendance.filter(status='late').count()
        excused_today = attendance.filter(status='excused').count()
        
        # Add Ghana education context to stats
        stats = [
            {'label': 'Total Students', 'value': total_students, 'color': 'primary', 'icon': 'people-fill'},
            {'label': 'Present Today', 'value': present_today, 'color': 'success', 'icon': 'check-circle-fill'},
            {'label': 'Absent Today', 'value': absent_today, 'color': 'danger', 'icon': 'x-circle-fill'},
            {'label': 'Late Today', 'value': late_today, 'color': 'warning', 'icon': 'clock-fill'},
            {'label': 'Excused Today', 'value': excused_today, 'color': 'info', 'icon': 'clipboard-check-fill'}
        ]
        
        # Add GES compliance stat if active term exists
        if active_term:
            ges_rate = self._calculate_school_ges_attendance_rate(active_term)
            ges_color = 'success' if ges_rate >= 80 else 'warning' if ges_rate >= 70 else 'danger'
            stats.append({
                'label': 'GES Attendance Rate', 
                'value': f'{ges_rate}%', 
                'color': ges_color, 
                'icon': 'clipboard-data-fill'
            })
        
        return stats

    def _calculate_class_stats(self, attendance):
        """Calculate statistics by class level"""
        class_stats = {}
        for class_level in CLASS_LEVEL_CHOICES:
            class_attendance = attendance.filter(student__class_level=class_level[0])
            stats = self._calculate_single_class_stats(class_attendance)
            class_stats[class_level[0]] = stats
            
        return class_stats

    def _calculate_single_class_stats(self, attendance):
        """Calculate statistics for a single class"""
        present = attendance.filter(status='present').count()
        absent = attendance.filter(status='absent').count()
        late = attendance.filter(status='late').count()
        excused = attendance.filter(status='excused').count()
        total = present + absent + late + excused
        
        if total > 0:
            present_percentage = round((present / total) * 100)
            absent_percentage = round((absent / total) * 100)
            late_percentage = round((late / total) * 100)
            excused_percentage = round((excused / total) * 100)
        else:
            present_percentage = absent_percentage = late_percentage = excused_percentage = 0
            
        return {
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'total': total,
            'present_percentage': present_percentage,
            'absent_percentage': absent_percentage,
            'late_percentage': late_percentage,
            'excused_percentage': excused_percentage,
        }

class AttendanceRecordView(AttendanceBaseView, GhanaEducationAttendanceMixin, View):
    """View for recording and viewing attendance records - Ghana Education System"""
    template_name = 'core/academics/attendance_record.html'

    def _get_filtered_attendance(self, date, active_term):
        """Filter attendance records for record view - OPTIMIZED VERSION"""
        queryset = StudentAttendance.objects.filter(
            date=date
        ).select_related('student', 'term', 'period').order_by(
            'student__class_level',
            'student__last_name',
            'student__first_name'
        )
        
        # Filter by active term if available
        if active_term:
            queryset = queryset.filter(term=active_term)
        
        if is_teacher(self.request.user):
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            queryset = queryset.filter(student__class_level__in=teacher_classes)
        
        return queryset

    def get(self, request):
        try:
            # Extract and validate filter parameters
            filters = self._extract_filters(request)
            
            # Enhanced parameter validation
            validation_result = self._validate_required_parameters(filters)
            if not validation_result['is_valid']:
                messages.info(request, validation_result['message'])
            
            # Get attendance data based on filters
            attendance_data = self._get_attendance_data(filters)
            
            # Add Ghana education context
            ghana_context = self._get_ghana_attendance_context(filters)
            
            # Prepare context
            context = {
                **filters,
                **attendance_data,
                **ghana_context,
                'status_choices': StudentAttendance.STATUS_CHOICES,
                'terms': AcademicTerm.objects.all().order_by('-start_date'),
                'periods': AttendancePeriod.objects.all().order_by('-start_date'),
                'class_levels': CLASS_LEVEL_CHOICES,
                'today': timezone.now().date(),
                # Add flags for parameter validation
                'has_required_params': validation_result['is_valid'],
                'validation_message': validation_result['message'],
            }
            return render(request, self.template_name, context)
            
        except Exception as e:
            messages.error(request, f"Error loading attendance: {str(e)}")
            return redirect(reverse('attendance_dashboard'))

    def _validate_required_parameters(self, filters):
        """Validate that all required parameters are present"""
        missing_params = []
        
        if not filters['selected_date']:
            missing_params.append('Date')
        if not filters['selected_term']:
            missing_params.append('Academic Term')
        if not filters['selected_class']:
            missing_params.append('Class Level')
        
        if missing_params:
            message = f"Please select {', '.join(missing_params)} to record attendance."
            return {'is_valid': False, 'message': message}
        
        return {'is_valid': True, 'message': 'All required parameters are selected.'}

    def _extract_filters(self, request):
        """Extract and validate filter parameters from GET request - ENHANCED VERSION"""
        term_id = request.GET.get('term')
        period_id = request.GET.get('period')
        date_str = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
        class_level = request.GET.get('class_level')
        
        # Initialize variables with proper defaults
        filters = {
            'selected_term': None,
            'selected_period': None,
            'selected_date': None,
            'selected_class': class_level,
            'selected_class_name': dict(CLASS_LEVEL_CHOICES).get(class_level, ''),
            'date_error': None,
            'class_error': None,
        }
        
        # Parse and validate date
        try:
            if date_str:
                filters['selected_date'] = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                filters['date_error'] = "Date is required"
        except (ValueError, TypeError):
            filters['date_error'] = "Invalid date format"
        
        # Validate term
        if term_id:
            try:
                filters['selected_term'] = AcademicTerm.objects.get(id=term_id)
            except AcademicTerm.DoesNotExist:
                filters['date_error'] = "Invalid term selected"
        else:
            # Try to get active term as default
            active_term = AcademicTerm.objects.filter(is_active=True).first()
            if active_term:
                filters['selected_term'] = active_term
        
        # Validate period if provided
        if period_id and filters['selected_term']:
            try:
                filters['selected_period'] = AttendancePeriod.objects.get(
                    id=period_id, 
                    term=filters['selected_term']
                )
            except AttendancePeriod.DoesNotExist:
                pass  # Period is optional, so we don't set an error
        
        # Validate date ranges if we have term and date
        if filters['selected_date'] and filters['selected_term']:
            self._validate_date_range(
                filters['selected_date'],
                filters['selected_term'].start_date,
                filters['selected_term'].end_date,
                'date_error',
                filters
            )
            
            if filters['selected_period']:
                self._validate_date_range(
                    filters['selected_date'],
                    filters['selected_period'].start_date,
                    filters['selected_period'].end_date,
                    'date_error',
                    filters
                )
        
        # Validate class assignment for teachers
        if (class_level and not filters['class_error'] 
                and is_teacher(self.request.user)):
            self._validate_teacher_class_assignment(class_level, filters)
            
        return filters

    def _validate_date_range(self, date, start, end, error_field, context):
        """Validate if date falls within specified range"""
        if date and (date < start or date > end):
            context[error_field] = f"Date must be between {start} and {end}"

    def _validate_teacher_class_assignment(self, class_level, context):
        """Validate if teacher is assigned to the specified class"""
        teacher_classes = ClassAssignment.objects.filter(
            teacher=self.request.user.teacher
        ).values_list('class_level', flat=True)
        
        if class_level not in teacher_classes:
            context['class_error'] = "You are not assigned to this class"

    def _get_attendance_data(self, filters):
        """Get attendance data based on filters"""
        data = {
            'students': None,
            'present_count': 0,
            'absent_count': 0,
            'late_count': 0,
            'excused_count': 0,
        }
        
        if filters['selected_class'] and not filters['class_error'] and not filters['date_error']:
            # Get active students for the class
            students = Student.objects.filter(
                class_level=filters['selected_class'],
                is_active=True
            ).order_by('last_name', 'first_name')
            
            if students.exists() and filters['selected_term']:
                self._enrich_student_data(students, filters)
                data.update(self._count_attendance_statuses(students))
            
            data['students'] = students
            
        return data

    def _enrich_student_data(self, students, filters):
        """Add attendance-related data to each student"""
        for student in students:
            # Get absence count for the current term
            student.absence_count = StudentAttendance.objects.filter(
                student=student,
                term=filters['selected_term'],
                status='absent'
            ).count()
            
            # Get GES attendance rate
            if filters['selected_term']:
                student.ges_attendance_rate = self.calculate_ges_attendance_rate(student, filters['selected_term'])
            
            # Get today's attendance if exists
            existing_attendance = StudentAttendance.objects.filter(
                student=student,
                date=filters['selected_date'],
                term=filters['selected_term']
            ).first()
            
            if existing_attendance:
                student.previous_status = existing_attendance.status
                student.previous_notes = existing_attendance.notes
            else:
                student.previous_status = None
                student.previous_notes = ''

    def _count_attendance_statuses(self, students):
        """Count attendance statuses for students"""
        counts = {
            'present_count': 0,
            'absent_count': 0,
            'late_count': 0,
            'excused_count': 0,
        }
        
        for student in students:
            if hasattr(student, 'previous_status') and student.previous_status:
                status = student.previous_status
                if status == 'present':
                    counts['present_count'] += 1
                elif status == 'absent':
                    counts['absent_count'] += 1
                elif status == 'late':
                    counts['late_count'] += 1
                elif status == 'excused':
                    counts['excused_count'] += 1
                    
        return counts

    def _get_ghana_attendance_context(self, filters):
        """Get Ghana-specific attendance context"""
        context = {}
        
        if filters['selected_date']:
            context['is_school_day'] = self.is_ghana_school_day(filters['selected_date'])
            context['day_type'] = 'School Day' if context['is_school_day'] else 'Non-School Day'
        
        if filters['selected_term']:
            context['term_progress'] = self._calculate_term_progress(filters['selected_term'])
        
        return context

    def _calculate_term_progress(self, term):
        """Calculate how far we are into the current term"""
        if not term:
            return 0
        
        today = timezone.now().date()
        
        if today < term.start_date:
            return 0
        elif today > term.end_date:
            return 100
        
        total_days = (term.end_date - term.start_date).days
        days_passed = (today - term.start_date).days
        
        if total_days > 0:
            progress = (days_passed / total_days) * 100
            return min(100, round(progress, 1))
        
        return 0

    def post(self, request):
        try:
            form_data = self._extract_form_data(request)
            self._validate_attendance_data(form_data)
            
            # Ghana-specific validation
            self._validate_ghana_attendance_rules(form_data)
            
            with transaction.atomic():
                self._process_attendance_records(form_data)
            
            # Build success redirect URL with all parameters
            redirect_url = self._build_success_redirect_url(form_data)
            messages.success(request, '✅ Attendance recorded successfully for GES records!')
            return redirect(redirect_url)
            
        except PermissionDenied as e:
            messages.error(request, str(e))
            return self._handle_error_redirect(request)
        except Exception as e:
            messages.error(request, f"Error recording attendance: {str(e)}")
            return self._handle_error_redirect(request)

    def _validate_ghana_attendance_rules(self, form_data):
        """Validate Ghana Education Service specific rules"""
        date = form_data['date']
        term = form_data['term']
        
        # Check if it's a school day
        if not self.is_ghana_school_day(date):
            messages.warning(
                form_data['request'], 
                f"Note: {date.strftime('%A, %B %d, %Y')} is not a regular school day."
            )
        
        # Check if date is within term boundaries
        if not (term.start_date <= date <= term.end_date):
            raise ValueError(
                f"Attendance date must be within {term} term dates: "
                f"{term.start_date} to {term.end_date}"
            )

    def _extract_form_data(self, request):
        """Extract and validate form data from POST request"""
        try:
            term_id = request.POST.get('term')
            if not term_id:
                raise ValueError("Term is required")
                
            term = AcademicTerm.objects.get(id=term_id)
            
            period_id = request.POST.get('period')
            period = None
            if period_id:
                period = AttendancePeriod.objects.get(id=period_id)
                
            date_str = request.POST.get('date')
            if not date_str:
                raise ValueError("Date is required")
                
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                raise ValueError("Invalid date format")
                
            class_level = request.POST.get('class_level')
            if not class_level:
                raise ValueError("Class level is required")
                
            # Validate teacher class assignment
            if is_teacher(request.user):
                teacher_classes = ClassAssignment.objects.filter(
                    teacher=request.user.teacher
                ).values_list('class_level', flat=True)
                
                if class_level not in teacher_classes:
                    raise PermissionDenied("Not authorized to record attendance for this class")
            
            students = Student.objects.filter(
                class_level=class_level,
                is_active=True
            ).order_by('last_name', 'first_name')
            
            if not students.exists():
                raise ValueError(f"No active students found for {dict(CLASS_LEVEL_CHOICES).get(class_level)}")
            
            return {
                'term': term,
                'period': period,
                'date': date,
                'class_level': class_level,
                'students': students,
                'request': request,
            }
            
        except AcademicTerm.DoesNotExist:
            raise ValueError("Invalid term selected")
        except AttendancePeriod.DoesNotExist:
            raise ValueError("Invalid period selected")
        except Student.DoesNotExist:
            raise ValueError("No students found for this class level")

    def _validate_attendance_data(self, form_data):
        """Validate attendance data before processing"""
        if (form_data['date'] < form_data['term'].start_date or 
                form_data['date'] > form_data['term'].end_date):
            raise ValueError(
                f"Date must be between {form_data['term'].start_date} "
                f"and {form_data['term'].end_date}"
            )
            
        if (form_data['period'] and 
                (form_data['date'] < form_data['period'].start_date or 
                 form_data['date'] > form_data['period'].end_date)):
            raise ValueError(
                f"Date must be between {form_data['period'].start_date} "
                f"and {form_data['period'].end_date}"
            )

    def _process_attendance_records(self, form_data):
        """Process attendance records for all students"""
        for student in form_data['students']:
            status_key = f"status_{student.id}"
            notes_key = f"notes_{student.id}"
            
            if status_key in form_data['request'].POST:
                status = form_data['request'].POST[status_key]
                notes = form_data['request'].POST.get(notes_key, '')
                
                # Create or update attendance record
                attendance, created = StudentAttendance.objects.update_or_create(
                    student=student,
                    date=form_data['date'],
                    term=form_data['term'],
                    period=form_data['period'],
                    defaults={
                        'status': status,
                        'notes': notes,
                        'recorded_by': form_data['request'].user
                    }
                )

    def _build_success_redirect_url(self, form_data):
        """Build redirect URL with all parameters after successful submission"""
        params = {
            'date': form_data['date'].strftime('%Y-%m-%d'),
            'term': form_data['term'].id,
            'class_level': form_data['class_level']
        }
        if form_data['period']:
            params['period'] = form_data['period'].id
        return reverse('attendance_record') + '?' + urlencode(params)

    def _handle_error_redirect(self, request):
        """Handle redirect when errors occur, preserving parameters"""
        try:
            params = {
                'date': request.POST.get('date'),
                'term': request.POST.get('term'),
                'class_level': request.POST.get('class_level')
            }
            if request.POST.get('period'):
                params['period'] = request.POST.get('period')
            return redirect(reverse('attendance_record') + '?' + urlencode(params))
        except:
            return redirect(reverse('attendance_dashboard'))

# Keep your existing views below (they remain the same)
class AttendancePeriodListView(AttendanceBaseView, ListView):
    """View for listing attendance periods"""
    model = AttendancePeriod
    template_name = 'core/academics/attendance_period_list.html'
    context_object_name = 'periods'
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('term').order_by(
            '-term__academic_year',
            '-term__term',
            '-start_date'
        )
        
        # Apply filters if specified
        term_id = self.request.GET.get('term_id')
        if term_id:
            queryset = queryset.filter(term_id=term_id)
            
        period_type = self.request.GET.get('period_type')
        if period_type:
            queryset = queryset.filter(period_type=period_type)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'terms': AcademicTerm.objects.all().order_by('-start_date'),
            'active_term': AcademicTerm.objects.filter(is_active=True).first(),
            'period_types': AttendancePeriod.PERIOD_CHOICES,
        })
        return context


class StudentAttendanceListView(LoginRequiredMixin, ListView):
    """View for students to see their own attendance records"""
    model = StudentAttendance
    template_name = 'core/academics/student_attendance_list.html'
    
    def get_queryset(self):
        if hasattr(self.request.user, 'student'):
            return StudentAttendance.objects.filter(
                student=self.request.user.student
            ).select_related('term', 'period').order_by('-date')
        return StudentAttendance.objects.none()


def load_periods(request):
    """AJAX view to load periods for a selected term"""
    term_id = request.GET.get('term_id')
    periods = AttendancePeriod.objects.filter(term_id=term_id).order_by('-start_date')
    return render(request, 'core/academics/attendance_period_dropdown_options.html', {
        'periods': periods
    })