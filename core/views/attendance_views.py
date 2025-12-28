from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.db.models import Count, Q, Case, When, IntegerField, FloatField
from django.db.models.functions import Cast
from datetime import datetime, date, timedelta
from urllib.parse import urlencode

from .base_views import *
from ..models import AcademicTerm, AttendancePeriod, StudentAttendance, Student, ClassAssignment, CLASS_LEVEL_CHOICES, Holiday
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
        import logging
        logger = logging.getLogger(__name__)
        user = self.request.user
        logger.info(f"AttendanceBaseView.test_func() - User: {user}")
        logger.info(f"Is teacher: {is_teacher(user)}")
        logger.info(f"Is admin: {is_admin(user)}")
        result = is_admin(user) or is_teacher(user)
        logger.info(f"Permission result: {result}")
        return result

class GhanaEducationAttendanceMixin:
    """
    Mixin implementing Ghana Education Service (GES) attendance policies
    """
    
    def is_ghana_school_day(self, date_obj):
        """Check if a date is a school day in Ghana (Monday-Friday)"""
        return date_obj.weekday() < 5  # 0=Monday, 4=Friday
    
    def get_ghana_academic_calendar(self):
        """
        Get Ghana academic calendar information
        This is a simplified version - you might want to enhance this
        """
        current_year = timezone.now().year
        return {
            'first_term': {
                'start': date(current_year, 1, 10),
                'end': date(current_year, 4, 15)
            },
            'second_term': {
                'start': date(current_year, 5, 10),
                'end': date(current_year, 8, 15)
            },
            'third_term': {
                'start': date(current_year, 9, 10),
                'end': date(current_year, 12, 15)
            }
        }
    
    def calculate_ges_attendance_rate(self, student, start_date, end_date):
        """
        Calculate attendance rate according to GES standards
        GES counts: Present, Late, and Excused Absence as 'present'
        Only Unexcused Absence counts as absent
        """
        # Get all attendance records for the period
        attendance_records = StudentAttendance.objects.filter(
            student=student,
            date__range=[start_date, end_date]
        )
        
        # Count actual school days in the period (excluding weekends and holidays)
        total_school_days = self.get_school_days_count(start_date, end_date)
        
        if total_school_days == 0:
            return 0.0
        
        # Count present days according to GES standards
        present_days = 0
        for record in attendance_records:
            if record.status in ['present', 'late', 'excused']:
                present_days += 1
        
        # Calculate percentage
        attendance_rate = (present_days / total_school_days) * 100
        return round(attendance_rate, 1)
    
    def get_school_days_count(self, start_date, end_date):
        """
        Calculate actual school days between two dates
        Excludes weekends and school holidays
        """
        from django.db.models import Q
        
        current_date = start_date
        school_days = 0
        
        # Get school holidays for this period
        holidays = Holiday.objects.filter(
            date__range=[start_date, end_date],
            is_school_holiday=True
        ).values_list('date', flat=True)
        
        while current_date <= end_date:
            # Check if it's a weekday (Monday-Friday)
            if current_date.weekday() < 5:  # 0=Monday, 4=Friday
                # Check if it's not a holiday
                if current_date not in holidays:
                    school_days += 1
            current_date += timedelta(days=1)
        
        return school_days
    
    def get_ges_attendance_status(self, attendance_rate):
        """
        Get GES attendance status description based on rate
        """
        if attendance_rate >= 90:
            return "Excellent"
        elif attendance_rate >= 80:
            return "Good" 
        elif attendance_rate >= 70:
            return "Satisfactory"
        elif attendance_rate >= 60:
            return "Needs Improvement"
        else:
            return "Unsatisfactory"
    
    def is_ges_compliant(self, attendance_rate):
        """
        Check if attendance meets GES minimum requirements
        """
        return attendance_rate >= 75.0


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
        """Filter attendance records with optimized queries"""
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
        
        # Use Student model's methods for attendance data (more efficient and consistent)
        for record in queryset:
            if active_term:
                # Get comprehensive attendance summary using Student model method
                attendance_summary = record.student.get_attendance_summary(active_term)
                
                record.term_attendance_rate = attendance_summary['attendance_rate']
                record.attendance_status = attendance_summary['attendance_status']
                record.is_ges_compliant = attendance_summary['is_ges_compliant']
                record.absence_count = attendance_summary['absence_count']
                record.total_attendance_days = attendance_summary['total_days']
                record.present_days = attendance_summary['present_days']
                record.late_count = attendance_summary['late_count']
                record.excused_count = attendance_summary['excused_count']
            else:
                # Set default values if no active term
                record.term_attendance_rate = 0.0
                record.attendance_status = 'No Data'
                record.is_ges_compliant = False
                record.absence_count = 0
                record.total_attendance_days = 0
                record.present_days = 0
                record.late_count = 0
                record.excused_count = 0
        
        return queryset

    def _get_ghana_education_context(self, active_term):
        """Get Ghana Education Service specific context data"""
        context = {}
        
        if active_term:
            # Calculate GES compliance statistics based on ACTUAL recorded days
            context['ges_attendance_rate'] = self._calculate_school_ges_attendance_rate(active_term)
            context['low_attendance_students'] = self._get_low_attendance_students(active_term)
            context['term_progress'] = self._calculate_term_progress(active_term)
            context['ges_compliance_rate'] = self._calculate_ges_compliance_rate(active_term)
        
        context['ghana_calendar'] = self.get_ghana_academic_calendar()
        context['is_school_day'] = self.is_ghana_school_day(timezone.now().date())
        
        return context

    def _calculate_school_ges_attendance_rate(self, term):
        """Calculate overall school attendance rate for GES reporting based on ACTUAL days - OPTIMIZED"""
        # Use aggregation for better performance with many students
        attendance_stats = StudentAttendance.objects.filter(
            term=term
        ).values('student_id').annotate(
            total_days=Count('id'),
            present_days=Count(
                Case(
                    When(status__in=['present', 'late', 'excused'], then=1),
                    output_field=IntegerField()
                )
            )
        ).annotate(
            student_rate=Case(
                When(total_days=0, then=0.0),
                default=Cast('present_days', FloatField()) / Cast('total_days', FloatField()) * 100.0,
                output_field=FloatField()
            )
        )
        
        if not attendance_stats:
            return 0
        
        # Calculate average of all student rates
        total_rate = sum(stat['student_rate'] for stat in attendance_stats)
        return round(total_rate / len(attendance_stats), 1)

    def _calculate_ges_compliance_rate(self, term):
        """Calculate percentage of students meeting GES 80% requirement - OPTIMIZED"""
        # Use aggregation for better performance
        attendance_stats = StudentAttendance.objects.filter(
            term=term
        ).values('student_id').annotate(
            total_days=Count('id'),
            present_days=Count(
                Case(
                    When(status__in=['present', 'late', 'excused'], then=1),
                    output_field=IntegerField()
                )
            )
        ).annotate(
            student_rate=Case(
                When(total_days=0, then=0.0),
                default=Cast('present_days', FloatField()) / Cast('total_days', FloatField()) * 100.0,
                output_field=FloatField()
            )
        )
        
        if not attendance_stats:
            return 0
        
        # Count students meeting GES requirement
        compliant_students = sum(1 for stat in attendance_stats if stat['student_rate'] >= 80.0)
        return round((compliant_students / len(attendance_stats)) * 100, 1)

    def _get_low_attendance_students(self, term, threshold=80):
        """Identify students with attendance below GES requirement (80%) - OPTIMIZED"""
        low_attendance = []
        
        # Get all active students
        students = Student.objects.filter(is_active=True).select_related('user')
        
        for student in students:
            # Use the Student model's method for consistency
            attendance_summary = student.get_attendance_summary(term)
            
            if attendance_summary['attendance_rate'] < threshold:
                low_attendance.append({
                    'student': student,
                    'attendance_rate': attendance_summary['attendance_rate'],
                    'attendance_status': attendance_summary['attendance_status'],
                    'class_level': student.get_class_level_display(),
                    'is_compliant': attendance_summary['is_ges_compliant'],
                    'total_days': attendance_summary['total_days'],
                    'present_days': attendance_summary['present_days'],
                    'absence_count': attendance_summary['absence_count']
                })
        
        # Sort by lowest attendance first
        low_attendance.sort(key=lambda x: x['attendance_rate'])
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
            compliance_rate = self._calculate_ges_compliance_rate(active_term)
            
            ges_color = 'success' if ges_rate >= 80 else 'warning' if ges_rate >= 70 else 'danger'
            compliance_color = 'success' if compliance_rate >= 80 else 'warning' if compliance_rate >= 70 else 'danger'
            
            stats.extend([
                {
                    'label': 'GES Attendance Rate', 
                    'value': f'{ges_rate}%', 
                    'color': ges_color, 
                    'icon': 'clipboard-data-fill'
                },
                {
                    'label': 'GES Compliance', 
                    'value': f'{compliance_rate}%', 
                    'color': compliance_color, 
                    'icon': 'shield-check'
                }
            ])
        
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

    def get(self, request):
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            logger.info("=" * 60)
            logger.info("DEBUG: AttendanceRecordView.get() START")
            logger.info("=" * 60)
            logger.info(f"User: {request.user}")
            logger.info(f"User ID: {request.user.id}")
            logger.info(f"Is teacher: {is_teacher(request.user)}")
            logger.info(f"Is admin: {is_admin(request.user)}")
            logger.info(f"GET params: {dict(request.GET)}")
            
            # Check if user has permission first
            if not (is_admin(request.user) or is_teacher(request.user)):
                logger.error(f"User {request.user} doesn't have permission!")
                messages.error(request, "You don't have permission to access attendance records")
                return redirect('attendance_dashboard')
            
            # Extract and validate filter parameters
            filters = self._extract_filters(request)
            logger.info(f"Filters extracted:")
            logger.info(f"  - Date: {filters.get('selected_date')}")
            logger.info(f"  - Term: {filters.get('selected_term')}")
            logger.info(f"  - Class: {filters.get('selected_class')}")
            logger.info(f"  - Period: {filters.get('selected_period')}")
            logger.info(f"  - Date Error: {filters.get('date_error')}")
            logger.info(f"  - Class Error: {filters.get('class_error')}")
            
            # Enhanced parameter validation
            validation_result = self._validate_required_parameters(filters)
            logger.info(f"Validation result: {validation_result}")
            
            if not validation_result['is_valid']:
                logger.warning(f"Validation failed: {validation_result['message']}")
                messages.info(request, validation_result['message'])
                # Don't redirect here - show the page with the message

            # ✅ Get students and their attendance data
            logger.info("Getting students attendance data...")
            attendance_data = self._get_students_attendance_data(filters)
            logger.info(f"Found {len(attendance_data.get('students', []))} students")
            logger.info(f"Attendance counts: {attendance_data.get('attendance_counts', {})}")
            
            # Add Ghana education context
            ghana_context = self._get_ghana_attendance_context(filters)
            logger.info(f"Ghana context: {ghana_context}")
            
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
            
            logger.info("=" * 60)
            logger.info("DEBUG: Rendering template")
            logger.info("=" * 60)
            
            return render(request, self.template_name, context)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error loading attendance: {str(e)}", exc_info=True)
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
        """Extract and validate filter parameters from GET request"""
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

    # ✅ ADD THIS NEW METHOD
    def _get_students_attendance_data(self, filters):
        """Get students and their attendance data for the selected filters"""
        if not all([filters['selected_class'], filters['selected_term'], filters['selected_date']]):
            return {
                'students': [],
                'attendance_counts': {
                    'present_count': 0,
                    'absent_count': 0,
                    'late_count': 0,
                    'excused_count': 0,
                }
            }
        
        # Get students for the selected class
        students = Student.objects.filter(
            class_level=filters['selected_class'],
            is_active=True
        ).order_by('last_name', 'first_name')
        
        # Enrich student data with attendance information
        self._enrich_student_data(students, filters)
        
        # Count attendance statuses
        attendance_counts = self._count_attendance_statuses(students)
        
        return {
            'students': students,
            'attendance_counts': attendance_counts,
        }

    # ⚠️ KEEP THIS METHOD (but it's not called from get() anymore)
    def _get_attendance_data(self, student, academic_year, term):
        """Get attendance data for a specific student - used by other views"""
        try:
            from core.utils import get_attendance_summary
            attendance_data = get_attendance_summary(student, academic_year, term)
        
            # If empty, try direct database query
            if not attendance_data or attendance_data.get('total_days') == 0:
                attendance_data = self._calculate_attendance_manually(student, academic_year, term)
            
        except (ImportError, AttributeError):
            attendance_data = self._calculate_attendance_manually(student, academic_year, term)
    
        return attendance_data

    def _calculate_attendance_manually(self, student, academic_year, term):
        """Calculate attendance data manually"""
        try:
            # Find academic term
            academic_term = AcademicTerm.objects.filter(
                academic_year=academic_year,
                term=term
            ).first()
        
            if not academic_term:
                return {
                    'present_days': 0,
                    'total_days': 0,
                    'attendance_rate': 0,
                    'absence_count': 0,
                    'late_count': 0,
                    'excused_count': 0
                }
        
            # Get attendance records
            attendance_records = StudentAttendance.objects.filter(
                student=student,
                date__range=[academic_term.start_date, academic_term.end_date]
            )
        
            total_days = attendance_records.count()
        
            if total_days == 0:
                # Estimate based on school days in term
                import datetime
                start_date = academic_term.start_date
                end_date = academic_term.end_date
                school_days = 0
                current_date = start_date
            
                while current_date <= end_date:
                    # Monday to Friday are school days (0=Monday, 4=Friday)
                    if current_date.weekday() < 5:
                        school_days += 1
                    current_date += datetime.timedelta(days=1)
            
                # Estimate 85% attendance as default
                estimated_present = int(school_days * 0.85)
                return {
                    'present_days': estimated_present,
                    'total_days': school_days,
                    'attendance_rate': 85.0,
                    'absence_count': school_days - estimated_present,
                    'late_count': 0,
                    'excused_count': 0
                }
        
            # Calculate actual attendance
            present_days = attendance_records.filter(
                Q(status='present') | Q(status='late') | Q(status='excused')
            ).count()
        
            absence_count = attendance_records.filter(status='absent').count()
            late_count = attendance_records.filter(status='late').count()
            excused_count = attendance_records.filter(status='excused').count()
        
            attendance_rate = round((present_days / total_days) * 100, 1) if total_days > 0 else 0
        
            return {
                'present_days': present_days,
                'total_days': total_days,
                'attendance_rate': attendance_rate,
                'absence_count': absence_count,
                'late_count': late_count,
                'excused_count': excused_count
            }
        
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating attendance: {str(e)}")
            return {
                'present_days': 0,
                'total_days': 0,
                'attendance_rate': 0,
                'absence_count': 0,
                'late_count': 0,
                'excused_count': 0
            }

    def _enrich_student_data(self, students, filters):
        """Add attendance-related data to each student"""
        for student in students:
            # Get absence count for the current term
            student.absence_count = StudentAttendance.objects.filter(
                student=student,
                term=filters['selected_term'],
                status='absent'
            ).count()
            
            # Use the Student model's methods for consistency and comprehensive data
            if filters['selected_term']:
                # Get comprehensive attendance data using Student model methods
                attendance_summary = student.get_attendance_summary(filters['selected_term'])
                
                student.ges_attendance_rate = attendance_summary['attendance_rate']
                student.attendance_status = attendance_summary['attendance_status']
                student.is_ges_compliant = attendance_summary['is_ges_compliant']
                student.total_attendance_days = attendance_summary['total_days']
                student.present_days = attendance_summary['present_days']
                student.late_count = attendance_summary['late_count']
                student.excused_count = attendance_summary['excused_count']
            
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