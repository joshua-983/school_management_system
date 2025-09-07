from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.db.models import Count, Q
from datetime import datetime
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


class AttendanceBaseView(LoginRequiredMixin, UserPassesTestMixin):
    """Base view for attendance-related views with common permissions"""
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)


class AttendanceDashboardView(AttendanceBaseView, TemplateView):
    """Dashboard view showing attendance overview and statistics"""
    template_name = 'core/academics/attendance_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        # Get terms and periods
        terms = AcademicTerm.objects.all().order_by('-start_date')
        active_term = terms.filter(is_active=True).first()
        periods = AttendancePeriod.objects.filter(term=active_term).order_by('-start_date') if active_term else []
        
        # Get filtered attendance data
        today_attendance = self._get_filtered_attendance(today)
        
        # Prepare statistics
        stats = self._calculate_attendance_stats(today_attendance)
        class_stats = self._calculate_class_stats(today_attendance)
        
        context.update({
            'today': today,
            'today_attendance': today_attendance,
            'terms': terms,
            'periods': periods,
            'class_levels': CLASS_LEVEL_CHOICES,  # FIXED: Use imported constant
            'status_choices': StudentAttendance.STATUS_CHOICES,
            'stats': stats,
            'class_stats': class_stats,
        })
        return context

    def _get_filtered_attendance(self, date):
        """Filter attendance records based on user role with proper ordering"""
        queryset = StudentAttendance.objects.filter(
            date=date
        ).select_related('student', 'term', 'period').order_by(
            'student__class_level',
            'student__last_name',
            'student__first_name'
        )
        
        if is_teacher(self.request.user):
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            queryset = queryset.filter(student__class_level__in=teacher_classes)
            
        return queryset

    def _calculate_attendance_stats(self, attendance):
        """Calculate and return attendance statistics"""
        total_students = Student.objects.count()
        present_today = attendance.filter(status='present').count()
        absent_today = attendance.filter(status='absent').count()
        late_today = attendance.filter(status='late').count()
        
        return [
            {'label': 'Total Students', 'value': total_students, 'color': 'primary', 'icon': 'people-fill'},
            {'label': 'Present Today', 'value': present_today, 'color': 'success', 'icon': 'check-circle-fill'},
            {'label': 'Absent Today', 'value': absent_today, 'color': 'danger', 'icon': 'x-circle-fill'},
            {'label': 'Late Today', 'value': late_today, 'color': 'warning', 'icon': 'clock-fill'}
        ]

    def _calculate_class_stats(self, attendance):
        """Calculate statistics by class level"""
        class_stats = {}
        for class_level in CLASS_LEVEL_CHOICES:  # FIXED: Use imported constant
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
        else:
            present_percentage = absent_percentage = late_percentage = 0
            
        return {
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'present_percentage': present_percentage,
            'absent_percentage': absent_percentage,
            'late_percentage': late_percentage,
        }
class AttendanceRecordView(AttendanceBaseView, View):
    """View for recording and viewing attendance records"""
    template_name = 'core/academics/attendance_record.html'

    def get(self, request):
        try:
            # Extract and validate filter parameters
            filters = self._extract_filters(request)
            
            # Get attendance data based on filters
            attendance_data = self._get_attendance_data(filters)
            
            # Prepare context
            context = {
                **filters,
                **attendance_data,
                'status_choices': StudentAttendance.STATUS_CHOICES,
            }
            return render(request, self.template_name, context)
            
        except Exception as e:
            messages.error(request, f"Error loading attendance: {str(e)}")
            return redirect(reverse('attendance_dashboard'))

    def post(self, request):
        try:
            form_data = self._extract_form_data(request)
            self._validate_attendance_data(form_data)
            
            with transaction.atomic():
                self._process_attendance_records(form_data)
            
            # Build success redirect URL with all parameters
            redirect_url = self._build_success_redirect_url(form_data)
            messages.success(request, 'Attendance recorded successfully')
            return redirect(redirect_url)
            
        except PermissionDenied as e:
            messages.error(request, str(e))
            return self._handle_error_redirect(request)
        except Exception as e:
            messages.error(request, f"Error recording attendance: {str(e)}")
            return self._handle_error_redirect(request)

    def _extract_filters(self, request):  # MOVED INSIDE THE CLASS
        """Extract and validate filter parameters from GET request"""
        term_id = request.GET.get('term')
        period_id = request.GET.get('period')
        date_str = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
        class_level = request.GET.get('class_level')
        
        # Initialize variables
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
            filters['selected_date'] = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            filters['date_error'] = "Invalid date format"
            return filters
        
        # Validate term and period
        if term_id:
            try:
                filters['selected_term'] = AcademicTerm.objects.get(id=term_id)
                self._validate_date_range(
                    filters['selected_date'],
                    filters['selected_term'].start_date,
                    filters['selected_term'].end_date,
                    'date_error',
                    filters
                )
                
                if period_id:
                    try:
                        filters['selected_period'] = AttendancePeriod.objects.get(id=period_id)
                        self._validate_date_range(
                            filters['selected_date'],
                            filters['selected_period'].start_date,
                            filters['selected_period'].end_date,
                            'date_error',
                            filters
                        )
                    except AttendancePeriod.DoesNotExist:
                        pass
            except AcademicTerm.DoesNotExist:
                pass
        
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
        }
        
        if filters['selected_class'] and not filters['class_error']:
            students = Student.objects.filter(
                class_level=filters['selected_class']
            ).order_by('last_name', 'first_name')
            
            if filters['selected_term']:
                self._enrich_student_data(students, filters)
                data.update(self._count_attendance_statuses(students))
            
            data['students'] = students
            
        return data

    def _enrich_student_data(self, students, filters):
        """Add attendance-related data to each student"""
        for student in students:
            # Get absence count
            student.absence_count = StudentAttendance.objects.filter(
                student=student,
                term=filters['selected_term'],
                status='absent'
            ).count()
            
            # Get previous attendance if exists
            existing_attendance = StudentAttendance.objects.filter(
                student=student,
                date=filters['selected_date'],
                term=filters['selected_term']
            ).first()
            
            if existing_attendance:
                student.previous_status = existing_attendance.status
                student.previous_notes = existing_attendance.notes

    def _count_attendance_statuses(self, students):
        """Count attendance statuses for students"""
        counts = {
            'present_count': 0,
            'absent_count': 0,
            'late_count': 0,
        }
        
        for student in students:
            if hasattr(student, 'previous_status'):
                status = student.previous_status
                if status == 'present':
                    counts['present_count'] += 1
                elif status == 'absent':
                    counts['absent_count'] += 1
                elif status == 'late':
                    counts['late_count'] += 1
                    
        return counts

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
                class_level=class_level
            ).order_by('last_name', 'first_name')
            
            if not students.exists():
                raise ValueError("No students found for this class level")
            
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
                StudentAttendance.objects.update_or_create(
                    student=student,
                    date=form_data['date'],
                    term=form_data['term'],
                    period=form_data['period'],
                    defaults={
                        'status': form_data['request'].POST[status_key],
                        'notes': form_data['request'].POST.get(notes_key, ''),
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

