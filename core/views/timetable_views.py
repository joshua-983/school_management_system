# timetable_views.py - FIXED VERSION
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse  # ADDED HttpResponse
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.conf import settings
from datetime import datetime, timedelta
from calendar import monthrange, monthcalendar
from collections import defaultdict
from core.permissions import is_admin, is_teacher, is_student, is_parent
from ..models import TimeSlot, Timetable, TimetableEntry, Teacher, Subject, Student, ClassAssignment, AcademicTerm
from ..forms import TimeSlotForm, TimetableForm, TimetableEntryForm, TimetableFilterForm
from ..models import CLASS_LEVEL_CHOICES


import logging
logger = logging.getLogger(__name__)

# ============================================================================
# TIME SLOT VIEWS (Admin Only)
# ============================================================================

class TimeSlotListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = TimeSlot
    template_name = 'core/timetable/timeslot_list.html'
    context_object_name = 'timeslots'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_queryset(self):
        return TimeSlot.objects.order_by('period_number')

class TimeSlotCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = TimeSlot
    form_class = TimeSlotForm
    template_name = 'core/timetable/timeslot_form.html'
    success_url = reverse_lazy('timeslot_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Time slot created successfully')
        return super().form_valid(form)

class TimeSlotUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = TimeSlot
    form_class = TimeSlotForm
    template_name = 'core/timetable/timeslot_form.html'
    success_url = reverse_lazy('timeslot_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Time slot updated successfully')
        return super().form_valid(form)

class TimeSlotDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = TimeSlot
    template_name = 'core/timetable/timeslot_confirm_delete.html'
    success_url = reverse_lazy('timeslot_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Time slot deleted successfully')
        return super().delete(request, *args, **kwargs)

# ============================================================================
# ADMIN TIMETABLE VIEWS
# ============================================================================

class TimetableListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Timetable
    template_name = 'core/timetable/admin/timetable_list.html'
    context_object_name = 'timetables'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_queryset(self):
        queryset = Timetable.objects.select_related('created_by').prefetch_related('entries')
        
        # Apply filters
        class_level = self.request.GET.get('class_level')
        academic_year = self.request.GET.get('academic_year')
        term = self.request.GET.get('term')
        day_of_week = self.request.GET.get('day_of_week')
        
        if class_level:
            queryset = queryset.filter(class_level=class_level)
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        if term:
            queryset = queryset.filter(term=term)
        if day_of_week:
            queryset = queryset.filter(day_of_week=day_of_week)
        
        return queryset.order_by('class_level', 'day_of_week')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['class_levels'] = CLASS_LEVEL_CHOICES
        
        # Generate academic years for dropdown (current and next 2 years)
        current_year = timezone.now().year
        context['academic_years'] = [
            f"{year}/{year+1}" for year in range(current_year-1, current_year+2)
        ]
        
        # Set default academic year
        context['default_academic_year'] = f"{current_year}/{current_year+1}"
        
        # Set default term
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        context['default_term'] = current_term.term if current_term else 1
        
        # Add day choices for the modal
        context['day_choices'] = [
            (0, 'Monday'),
            (1, 'Tuesday'),
            (2, 'Wednesday'),
            (3, 'Thursday'),
            (4, 'Friday'),
            (5, 'Saturday'),
        ]
        
        return context

class TimetableCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Timetable
    form_class = TimetableForm
    template_name = 'core/timetable/admin/timetable_form.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Timetable created successfully')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('timetable_manage', kwargs={'pk': self.object.pk})

class TimetableDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Timetable
    template_name = 'core/timetable/admin/timetable_detail.html'
    context_object_name = 'timetable'
    
    def test_func(self):
        timetable = self.get_object()
        if is_admin(self.request.user):
            return True
        if is_teacher(self.request.user):
            # Check if teacher teaches this class
            return ClassAssignment.objects.filter(
                class_level=timetable.class_level,
                teacher=self.request.user.teacher
            ).exists()
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['timeslots'] = TimeSlot.objects.order_by('period_number')
        context['entries'] = self.object.entries.select_related(
            'time_slot', 'subject', 'teacher'
        ).order_by('time_slot__period_number')
        context['is_admin'] = is_admin(self.request.user)
        return context

class TimetableUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Allow teachers and admins to edit timetables"""
    model = Timetable
    form_class = TimetableForm
    template_name = 'core/timetable/admin/timetable_form.html'
    
    def test_func(self):
        timetable = self.get_object()
        if is_admin(self.request.user):
            return True
        if is_teacher(self.request.user):
            # Check if teacher teaches this class
            return ClassAssignment.objects.filter(
                class_level=timetable.class_level,
                teacher=self.request.user.teacher
            ).exists()
        return False
    
    def form_valid(self, form):
        messages.success(self.request, 'Timetable updated successfully')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('timetable_detail', kwargs={'pk': self.object.pk})

class TimetableManageView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'core/timetable/admin/timetable_manage.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get(self, request, pk):
        timetable = get_object_or_404(Timetable, pk=pk)
        timeslots = TimeSlot.objects.order_by('period_number')
        entries = timetable.entries.select_related('time_slot', 'subject', 'teacher')
        
        # Create forms for each time slot
        entry_forms = []
        for timeslot in timeslots:
            try:
                entry = entries.get(time_slot=timeslot)
                form = TimetableEntryForm(instance=entry, timetable=timetable)
            except TimetableEntry.DoesNotExist:
                form = TimetableEntryForm(
                    initial={'time_slot': timeslot},
                    timetable=timetable
                )
            entry_forms.append((timeslot, form))
        
        context = {
            'timetable': timetable,
            'entry_forms': entry_forms,
            'timeslots': timeslots,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, pk):
        timetable = get_object_or_404(Timetable, pk=pk)
        timeslots = TimeSlot.objects.order_by('period_number')
        
        for timeslot in timeslots:
            entry_id = request.POST.get(f'entry_{timeslot.id}')
            subject_id = request.POST.get(f'timeslot_{timeslot.id}_subject')
            teacher_id = request.POST.get(f'timeslot_{timeslot.id}_teacher')
            classroom = request.POST.get(f'timeslot_{timeslot.id}_classroom', '')
            
            # FIX: Check if checkbox is checked (returns 'true' when checked, otherwise None)
            is_break = request.POST.get(f'timeslot_{timeslot.id}_is_break') == 'true'
            
            break_name = request.POST.get(f'timeslot_{timeslot.id}_break_name', '')
            
            if is_break:
                # Handle break period
                if entry_id:
                    try:
                        entry = TimetableEntry.objects.get(id=entry_id, timetable=timetable)
                        entry.is_break = True
                        entry.break_name = break_name
                        entry.subject = None
                        entry.teacher = None
                        entry.classroom = ''
                        entry.save()
                    except TimetableEntry.DoesNotExist:
                        TimetableEntry.objects.create(
                            timetable=timetable,
                            time_slot=timeslot,
                            is_break=True,
                            break_name=break_name
                        )
                else:
                    TimetableEntry.objects.create(
                        timetable=timetable,
                        time_slot=timeslot,
                        is_break=True,
                        break_name=break_name
                    )
            elif subject_id and teacher_id:
                # Handle class period
                subject = get_object_or_404(Subject, id=subject_id)
                teacher = get_object_or_404(Teacher, id=teacher_id)
                
                if entry_id:
                    entry = get_object_or_404(TimetableEntry, id=entry_id, timetable=timetable)
                    entry.subject = subject
                    entry.teacher = teacher
                    entry.classroom = classroom
                    entry.is_break = False
                    entry.break_name = ''
                    entry.save()
                else:
                    TimetableEntry.objects.create(
                        timetable=timetable,
                        time_slot=timeslot,
                        subject=subject,
                        teacher=teacher,
                        classroom=classroom,
                        is_break=False
                    )
            else:
                # If neither break nor valid class, delete existing entry if any
                if entry_id:
                    try:
                        entry = TimetableEntry.objects.get(id=entry_id, timetable=timetable)
                        entry.delete()
                    except TimetableEntry.DoesNotExist:
                        pass
        
        messages.success(request, 'Timetable updated successfully')
        return redirect('timetable_detail', pk=timetable.pk)

class TimetableDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Timetable
    template_name = 'core/timetable/admin/timetable_confirm_delete.html'
    success_url = reverse_lazy('timetable_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Timetable deleted successfully')
        return super().delete(request, *args, **kwargs)

# ============================================================================
# TEACHER TIMETABLE VIEWS
# ============================================================================

class TeacherTimetableListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Teacher's view of all timetables for their classes"""
    model = Timetable
    template_name = 'core/timetable/teacher/timetable_list.html'
    context_object_name = 'timetables'
    
    def test_func(self):
        return is_teacher(self.request.user)
    
    def get_queryset(self):
        teacher = self.request.user.teacher
        
        # Get classes assigned to this teacher
        assigned_classes = ClassAssignment.objects.filter(
            teacher=teacher
        ).values_list('class_level', flat=True).distinct()
        
        # Get timetables for assigned classes
        queryset = Timetable.objects.filter(
            class_level__in=assigned_classes,
            is_active=True
        ).select_related('created_by').prefetch_related('entries')
        
        # Apply filters
        class_level = self.request.GET.get('class_level')
        academic_year = self.request.GET.get('academic_year')
        term = self.request.GET.get('term')
        day_of_week = self.request.GET.get('day_of_week')
        
        if class_level:
            queryset = queryset.filter(class_level=class_level)
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        if term:
            queryset = queryset.filter(term=term)
        if day_of_week:
            queryset = queryset.filter(day_of_week=day_of_week)
        
        return queryset.order_by('class_level', 'day_of_week')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.request.user.teacher
        
        # Get teacher's assigned classes for filter dropdown
        assigned_classes = ClassAssignment.objects.filter(
            teacher=teacher
        ).values_list('class_level', flat=True).distinct()
        
        context['class_levels'] = [
            (code, name) for code, name in CLASS_LEVEL_CHOICES 
            if code in assigned_classes
        ]
        
        # Generate academic years
        current_year = timezone.now().year
        context['academic_years'] = [
            f"{year}/{year+1}" for year in range(current_year-1, current_year+2)
        ]
        
        # Set default academic year
        context['default_academic_year'] = f"{current_year}/{current_year+1}"
        
        # Set default term
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        context['default_term'] = current_term.term if current_term else 1
        
        return context

class TeacherTimetableDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Teacher's detailed view of a specific timetable"""
    model = Timetable
    template_name = 'core/timetable/teacher/timetable_detail.html'
    context_object_name = 'timetable'
    
    def test_func(self):
        timetable = self.get_object()
        teacher = self.request.user.teacher
        
        # Check if teacher teaches this class
        return ClassAssignment.objects.filter(
            class_level=timetable.class_level,
            teacher=teacher
        ).exists()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['timeslots'] = TimeSlot.objects.order_by('period_number')
        context['entries'] = self.object.entries.select_related(
            'time_slot', 'subject', 'teacher'
        ).order_by('time_slot__period_number')
        context['is_admin'] = is_admin(self.request.user)
        return context

class TeacherTimetableManageView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Teacher's view to manage their class timetables (read-only for now)"""
    template_name = 'core/timetable/teacher/timetable_manage.html'
    
    def test_func(self):
        return is_teacher(self.request.user)
    
    def get(self, request, pk):
        timetable = get_object_or_404(Timetable, pk=pk)
        teacher = request.user.teacher
        
        # Verify teacher teaches this class
        if not ClassAssignment.objects.filter(
            class_level=timetable.class_level,
            teacher=teacher
        ).exists():
            messages.error(request, 'You do not have permission to view this timetable')
            return redirect('teacher_timetable_list')
        
        timeslots = TimeSlot.objects.order_by('period_number')
        entries = timetable.entries.select_related('time_slot', 'subject', 'teacher')
        
        context = {
            'timetable': timetable,
            'timeslots': timeslots,
            'entries': entries,
        }
        return render(request, self.template_name, context)

# ============================================================================
# TIMETABLE CALENDAR VIEW
# ============================================================================

class TimetableCalendarView(LoginRequiredMixin, TemplateView):
    """View for displaying timetable calendar"""
    template_name = 'core/timetable/calendar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current date
        now = timezone.now()
        context['current_month'] = now.strftime('%B')
        context['current_year'] = now.year
        
        # Get user role
        user = self.request.user
        context['is_admin'] = is_admin(user)
        context['is_teacher'] = is_teacher(user)
        context['is_student'] = is_student(user)
        context['is_parent'] = is_parent(user)
        
        # Get current academic year and term
        current_year = timezone.now().year
        next_year = current_year + 1
        academic_year = f"{current_year}/{next_year}"
        
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        term = current_term.term if current_term else 1
        
        context['academic_year'] = academic_year
        context['term'] = term
        
        # Get calendar weeks for current month
        context['calendar_weeks'] = self.get_calendar_weeks(now.year, now.month)
        
        # Get today's events
        context['today_events'] = self.get_today_events(user)
        
        # Get upcoming events
        context['upcoming_events'] = self.get_upcoming_events(user)
        
        # Get event categories
        context['event_categories'] = self.get_event_categories(user)
        
        # Get stats
        context.update(self.get_calendar_stats(now.year, now.month, user))
        
        return context
    
    def get_calendar_weeks(self, year, month):
        """Generate calendar weeks with events"""
        # Create calendar matrix
        cal = monthcalendar(year, month)
        weeks = []
        
        # Get events for this month based on user role
        user = self.request.user
        events = self.get_month_events(year, month, user)
        
        # Organize events by day
        events_by_day = defaultdict(list)
        for event in events:
            event_day = event['date'].day
            events_by_day[event_day].append(event)
        
        # Build calendar weeks
        for week in cal:
            week_days = []
            for day in week:
                if day == 0:
                    week_days.append({
                        'day': None,
                        'date': None,
                        'events': [],
                        'is_current_month': False,
                        'is_today': False,
                        'is_weekend': False
                    })
                else:
                    date = datetime(year, month, day).date()
                    is_today = date == timezone.now().date()
                    is_weekend = date.weekday() >= 5  # Saturday=5, Sunday=6
                    
                    week_days.append({
                        'day': day,
                        'date': date,
                        'events': events_by_day.get(day, []),
                        'is_current_month': True,
                        'is_today': is_today,
                        'is_weekend': is_weekend
                    })
            weeks.append(week_days)
        
        return weeks
    
    def get_month_events(self, year, month, user):
        """Get events for a specific month based on user role"""
        events = []
        
        # Get date range for the month
        _, last_day = monthrange(year, month)
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, last_day).date()
        
        if is_admin(user):
            # Admin sees all events
            timetable_entries = TimetableEntry.objects.filter(
                timetable__academic_year=self.get_academic_year(),
                timetable__term=self.get_current_term(),
                timetable__is_active=True
            ).select_related('timetable', 'subject', 'teacher', 'time_slot')
            
            for entry in timetable_entries:
                events.append(self.format_timetable_entry(entry))
        
        elif is_teacher(user):
            teacher = user.teacher
            timetable_entries = TimetableEntry.objects.filter(
                teacher=teacher,
                timetable__academic_year=self.get_academic_year(),
                timetable__term=self.get_current_term(),
                timetable__is_active=True,
                is_break=False
            ).select_related('timetable', 'subject', 'time_slot')
            
            for entry in timetable_entries:
                events.append(self.format_timetable_entry(entry))
        
        elif is_student(user):
            student = user.student
            timetable_entries = TimetableEntry.objects.filter(
                timetable__class_level=student.class_level,
                timetable__academic_year=self.get_academic_year(),
                timetable__term=self.get_current_term(),
                timetable__is_active=True,
                is_break=False
            ).select_related('timetable', 'subject', 'teacher', 'time_slot')
            
            for entry in timetable_entries:
                events.append(self.format_timetable_entry(entry))
        
        return events
    
    def format_timetable_entry(self, entry):
        """Format timetable entry for calendar display"""
        is_current = False
        
        # Check if this is the current period
        now = timezone.now()
        if entry.time_slot.start_time <= now.time() <= entry.time_slot.end_time:
            is_current = True
        
        return {
            'id': f"timetable_{entry.id}",
            'title': entry.subject.name if entry.subject else entry.break_name,
            'title_short': (entry.subject.code if entry.subject else entry.break_name[:3])[:10],
            'time': f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}",
            'date': datetime.combine(timezone.now().date(), entry.time_slot.start_time),
            'teacher': entry.teacher.get_full_name() if entry.teacher else '',
            'classroom': entry.classroom or '',
            'description': f"{entry.subject.name} with {entry.teacher.get_full_name()}" if entry.subject and entry.teacher else '',
            'color': '#0d6efd' if not entry.is_break else '#6c757d',
            'is_break': entry.is_break,
            'is_current': is_current
        }
    
    def get_today_events(self, user):
        """Get events for today"""
        today = timezone.now().date()
        events = []
        
        if is_admin(user):
            entries = TimetableEntry.objects.filter(
                timetable__academic_year=self.get_academic_year(),
                timetable__term=self.get_current_term(),
                timetable__day_of_week=today.weekday(),
                timetable__is_active=True
            ).select_related('timetable', 'subject', 'teacher', 'time_slot')
        elif is_teacher(user):
            teacher = user.teacher
            entries = TimetableEntry.objects.filter(
                teacher=teacher,
                timetable__academic_year=self.get_academic_year(),
                timetable__term=self.get_current_term(),
                timetable__day_of_week=today.weekday(),
                timetable__is_active=True,
                is_break=False
            ).select_related('timetable', 'subject', 'time_slot')
        elif is_student(user):
            student = user.student
            entries = TimetableEntry.objects.filter(
                timetable__class_level=student.class_level,
                timetable__academic_year=self.get_academic_year(),
                timetable__term=self.get_current_term(),
                timetable__day_of_week=today.weekday(),
                timetable__is_active=True,
                is_break=False
            ).select_related('timetable', 'subject', 'teacher', 'time_slot')
        else:
            entries = TimetableEntry.objects.none()
        
        for entry in entries:
            events.append({
                'id': f"timetable_{entry.id}",
                'title': entry.subject.name if entry.subject else entry.break_name,
                'time': f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}",
                'details': f"{entry.timetable.get_class_level_display()} • {entry.classroom or 'TBA'}"
            })
        
        return events[:5]
    
    def get_upcoming_events(self, user):
        """Get upcoming events for the next 7 days"""
        events = []
        today = timezone.now().date()
        
        # For simplicity, get events for the next week
        for i in range(1, 8):
            day = today + timedelta(days=i)
            
            # Get events for this day (this is simplified - you might want to query differently)
            # For now, return a placeholder
            events.append({
                'id': f"event_{i}",
                'date': day.strftime('%b %d'),
                'title': f"Class Day {i}",
                'details': f"Regular classes"
            })
        
        return events[:3]
    
    def get_event_categories(self, user):
        """Get event categories based on user role"""
        categories = [
            {'id': 'class', 'name': 'Class Periods', 'color': '#0d6efd', 'count': 0},
            {'id': 'break', 'name': 'Breaks', 'color': '#6c757d', 'count': 0},
            {'id': 'exam', 'name': 'Exams', 'color': '#dc3545', 'count': 0},
        ]
        
        if is_admin(user):
            categories[0]['count'] = TimetableEntry.objects.filter(
                is_break=False,
                timetable__is_active=True
            ).count()
            categories[1]['count'] = TimetableEntry.objects.filter(
                is_break=True,
                timetable__is_active=True
            ).count()
        
        return categories
    
    def get_calendar_stats(self, year, month, user):
        """Get calendar statistics"""
        return {
            'total_events': 0,
            'class_days': 20,
            'busy_days': 15,
            'free_days': 5,
        }
    
    def get_academic_year(self):
        """Get current academic year"""
        current_year = timezone.now().year
        next_year = current_year + 1
        return f"{current_year}/{next_year}"
    
    def get_current_term(self):
        """Get current term"""
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        return current_term.term if current_term else 1

# ============================================================================
# AJAX VIEWS FOR TIMETABLE MANAGEMENT
# ============================================================================

@login_required
@user_passes_test(is_admin)
def get_subjects_for_class(request, class_level):
    """AJAX endpoint to get subjects for a specific class level"""
    logger.debug(f"get_subjects_for_class called with class_level={class_level}")
    try:
        # Get all subjects (you might want to filter by class level in the future)
        subjects = Subject.objects.all().order_by('name')
        
        data = {
            'subjects': [
                {
                    'id': subject.id,
                    'name': subject.name,
                    'code': subject.code,
                    'description': subject.description or '',
                    'color': '#0d6efd'
                }
                for subject in subjects
            ]
        }
        logger.debug(f"Returning {len(subjects)} subjects")
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error in get_subjects_for_class: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@user_passes_test(is_admin)
def get_available_teachers(request):
    """AJAX endpoint to get available teachers"""
    logger.debug(f"get_available_teachers called with query params: {request.GET}")
    try:
        class_level = request.GET.get('class_level', '')
        
        # Get all teachers
        teachers = Teacher.objects.select_related('user').all()
        
        data = {
            'teachers': [
                {
                    'id': teacher.id,
                    'name': teacher.user.get_full_name(),
                    'email': teacher.user.email,
                    'subjects': list(teacher.subjects.values_list('name', flat=True)),
                    'qualifications': teacher.qualifications or '',
                    'is_active': teacher.user.is_active
                }
                for teacher in teachers
            ]
        }
        logger.debug(f"Returning {len(teachers)} teachers")
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error in get_available_teachers: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# ============================================================================
# CALENDAR AJAX VIEWS
# ============================================================================

@login_required
def calendar_data(request):
    """AJAX endpoint for calendar data"""
    year = request.GET.get('year', timezone.now().year)
    month = request.GET.get('month', timezone.now().month)
    
    # Get calendar weeks
    view = TimetableCalendarView()
    view.request = request
    calendar_weeks = view.get_calendar_weeks(int(year), int(month))
    
    return JsonResponse({
        'calendar_weeks': calendar_weeks,
        'stats': view.get_calendar_stats(int(year), int(month), request.user)
    })

@login_required
def day_events(request):
    """AJAX endpoint for day events"""
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'error': 'Date required'}, status=400)
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_of_week = date.weekday()
        
        # Get events for this day
        user = request.user
        events = []
        
        if is_admin(user):
            entries = TimetableEntry.objects.filter(
                timetable__academic_year=TimetableCalendarView().get_academic_year(),
                timetable__term=TimetableCalendarView().get_current_term(),
                timetable__day_of_week=day_of_week,
                timetable__is_active=True
            ).select_related('timetable', 'subject', 'teacher', 'time_slot')
        elif is_teacher(user):
            teacher = user.teacher
            entries = TimetableEntry.objects.filter(
                teacher=teacher,
                timetable__academic_year=TimetableCalendarView().get_academic_year(),
                timetable__term=TimetableCalendarView().get_current_term(),
                timetable__day_of_week=day_of_week,
                timetable__is_active=True,
                is_break=False
            ).select_related('timetable', 'subject', 'time_slot')
        elif is_student(user):
            student = user.student
            entries = TimetableEntry.objects.filter(
                timetable__class_level=student.class_level,
                timetable__academic_year=TimetableCalendarView().get_academic_year(),
                timetable__term=TimetableCalendarView().get_current_term(),
                timetable__day_of_week=day_of_week,
                timetable__is_active=True,
                is_break=False
            ).select_related('timetable', 'subject', 'teacher', 'time_slot')
        else:
            entries = TimetableEntry.objects.none()
        
        for entry in entries:
            events.append({
                'id': f"timetable_{entry.id}",
                'title': entry.subject.name if entry.subject else entry.break_name,
                'time': f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}",
                'details': f"{entry.timetable.get_class_level_display()} • {entry.teacher.get_full_name() if entry.teacher else 'Break'} • {entry.classroom or 'TBA'}"
            })
        
        return JsonResponse({'events': events})
    
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

@login_required
def event_details(request, event_id):
    """AJAX endpoint for event details"""
    if event_id.startswith('timetable_'):
        try:
            entry_id = int(event_id.split('_')[1])
            entry = get_object_or_404(TimetableEntry, id=entry_id)
            
            data = {
                'title': entry.subject.name if entry.subject else entry.break_name,
                'date_time': f"{entry.timetable.get_day_of_week_display()} • {entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}",
                'description': f"Class: {entry.timetable.get_class_level_display()}",
                'teacher': entry.teacher.get_full_name() if entry.teacher else 'N/A',
                'classroom': entry.classroom or 'TBA',
                'color': '#0d6efd' if not entry.is_break else '#6c757d',
                'tags': ['Class Period'] if not entry.is_break else ['Break']
            }
            return JsonResponse(data)
        except (ValueError, IndexError):
            pass
    
    return JsonResponse({
        'title': 'Event Details',
        'date_time': 'N/A',
        'description': 'No details available',
        'teacher': 'N/A',
        'classroom': 'N/A',
        'color': '#6c757d',
        'tags': ['General']
    })

@login_required
def export_calendar(request):
    """Export calendar as ICS file"""
    # Simple ICS file generation
    ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//School//Timetable Calendar//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH

BEGIN:VEVENT
SUMMARY:School Calendar
DTSTART:20241209T080000Z
DTEND:20241209T170000Z
DESCRIPTION:School timetable calendar export
LOCATION:School
END:VEVENT

END:VCALENDAR"""
    
    response = HttpResponse(ics_content, content_type='text/calendar')
    response['Content-Disposition'] = 'attachment; filename="timetable-calendar.ics"'
    return response

# ============================================================================
# STUDENT & PARENT TIMETABLE VIEWS
# ============================================================================

class StudentTimetableView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/timetable/student/student_timetable.html'
    
    def test_func(self):
        return is_student(self.request.user) or is_parent(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if is_student(self.request.user):
            student = self.request.user.student
            class_level = student.class_level
            context['student'] = student
            context['user_type'] = 'student'
        else:
            # For parents, get the first child's class level
            children = self.request.user.parentguardian.student.all()
            if children.exists():
                student = children.first()
                class_level = student.class_level
                context['student'] = student
                context['user_type'] = 'parent'
                context['children'] = children
            else:
                class_level = None
        
        if class_level:
            # Get current academic year and term
            current_year = timezone.now().year
            next_year = current_year + 1
            academic_year = f"{current_year}/{next_year}"
            
            # Try to get current term
            current_term = AcademicTerm.objects.filter(is_active=True).first()
            term = current_term.term if current_term else 1
            
            # Get timetable for the week
            timetables = Timetable.objects.filter(
                class_level=class_level,
                academic_year=academic_year,
                term=term,
                is_active=True
            ).prefetch_related(
                'entries__time_slot',
                'entries__subject',
                'entries__teacher'
            ).order_by('day_of_week')
            
            # Organize by day
            weekly_timetable = {}
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            
            for day_num, day_name in enumerate(days_order):
                try:
                    timetable = timetables.get(day_of_week=day_num)
                    # Order entries by time slot period number
                    entries = timetable.entries.select_related(
                        'time_slot', 'subject', 'teacher'
                    ).order_by('time_slot__period_number')
                    weekly_timetable[day_name] = entries
                except Timetable.DoesNotExist:
                    weekly_timetable[day_name] = []
            
            # Get all time slots for the weekly overview
            time_slots = TimeSlot.objects.order_by('period_number')
            time_slot_list = []
            
            for slot in time_slots:
                time_slot_list.append({
                    'id': slot.id,
                    'period': slot.period_number,
                    'time_range': f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}",
                    'is_break': slot.is_break,
                    'break_name': slot.break_name
                })
            
            context.update({
                'weekly_timetable': weekly_timetable,
                'time_slots': time_slot_list,
                'days_order': days_order,
                'class_level': class_level,
                'academic_year': academic_year,
                'term': term,
                'timetables_by_day': weekly_timetable
            })
        
        return context

# ============================================================================
# COMMON VIEWS (All Users)
# ============================================================================

class TimetableView(LoginRequiredMixin, TemplateView):
    """Main timetable view that redirects based on user role"""
    template_name = 'core/timetable/index.html'
    
    def get(self, request, *args, **kwargs):
        if is_admin(request.user):
            return redirect('timetable_list')
        elif is_teacher(request.user):
            return redirect('teacher_timetable_list')
        elif is_student(request.user):
            return redirect('student_timetable_view')
        elif is_parent(request.user):
            return redirect('student_timetable_view')
        else:
            messages.info(request, "Please log in to view timetables")
            return redirect('login')

class TeacherTimetableView(LoginRequiredMixin, TemplateView):
    """Teacher's personal weekly schedule view"""
    template_name = 'core/timetable/teacher/teacher_schedule.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if not is_teacher(self.request.user):
            return context
        
        teacher = self.request.user.teacher
        context['teacher'] = teacher
        
        # Get current academic year and term
        current_year = timezone.now().year
        next_year = current_year + 1
        academic_year = f"{current_year}/{next_year}"
        
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        term = current_term.term if current_term else 1
        
        # Get all timetable entries for this teacher
        entries = TimetableEntry.objects.filter(
            teacher=teacher,
            timetable__academic_year=academic_year,
            timetable__term=term,
            timetable__is_active=True,
            is_break=False
        ).select_related(
            'timetable', 'subject', 'time_slot', 'teacher__user'
        ).order_by('timetable__day_of_week', 'time_slot__period_number')
        
        # Group entries by day of week
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        periods_by_day = {}
        
        for entry in entries:
            day_name = days_order[entry.timetable.day_of_week]
            if day_name not in periods_by_day:
                periods_by_day[day_name] = []
            
            # Add current period flag
            now = timezone.now()
            start_datetime = timezone.make_aware(
                timezone.datetime.combine(now.date(), entry.time_slot.start_time)
            )
            end_datetime = timezone.make_aware(
                timezone.datetime.combine(now.date(), entry.time_slot.end_time)
            )
            
            entry.is_current = start_datetime <= now <= end_datetime
            periods_by_day[day_name].append(entry)
        
        context['periods_by_day'] = periods_by_day
        context['days_order'] = days_order
        
        # Calculate statistics
        context['total_periods'] = entries.count()
        context['classes_teaching'] = list(set([entry.timetable.get_class_level_display() for entry in entries]))
        context['subjects_teaching'] = list(set([entry.subject.name for entry in entries]))
        
        # Generate time slots for weekly overview
        time_slots = TimeSlot.objects.order_by('period_number')
        context['time_slots'] = [f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}" for slot in time_slots]
        
        return context

# ============================================================================
# AJAX & UTILITY VIEWS
# ============================================================================

@login_required
def get_timetable_entries(request):
    """AJAX view to get timetable entries for a specific class and day"""
    class_level = request.GET.get('class_level')
    day_of_week = request.GET.get('day_of_week')
    academic_year = request.GET.get('academic_year')
    term = request.GET.get('term')
    
    if not all([class_level, day_of_week, academic_year, term]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        timetable = Timetable.objects.get(
            class_level=class_level,
            day_of_week=day_of_week,
            academic_year=academic_year,
            term=term
        )
        entries = timetable.entries.select_related('time_slot', 'subject', 'teacher')
        
        data = {
            'entries': [
                {
                    'id': entry.id,
                    'time_slot': str(entry.time_slot),
                    'subject': entry.subject.name,
                    'teacher': entry.teacher.get_full_name(),
                    'classroom': entry.classroom,
                    'is_break': entry.is_break
                }
                for entry in entries.order_by('time_slot__period_number')
            ]
        }
        return JsonResponse(data)
    except Timetable.DoesNotExist:
        return JsonResponse({'error': 'Timetable not found'}, status=404)

@login_required
@user_passes_test(is_admin)
def generate_weekly_timetable(request):
    """Generate weekly timetable for a class"""
    if request.method == 'POST':
        class_level = request.POST.get('class_level')
        academic_year = request.POST.get('academic_year')
        term = request.POST.get('term')
        
        if not all([class_level, academic_year, term]):
            messages.error(request, 'Please provide all required fields')
            return redirect('timetable_list')
        
        # Validate academic year format
        import re
        if not re.match(r'^\d{4}/\d{4}$', academic_year):
            messages.error(request, 'Academic year must be in format YYYY/YYYY (e.g., 2024/2025)')
            return redirect('timetable_list')
        
        # Validate term
        try:
            term = int(term)
            if term not in [1, 2, 3]:
                raise ValueError
        except ValueError:
            messages.error(request, 'Term must be 1, 2, or 3')
            return redirect('timetable_list')
        
        # Create timetables for all days of the week
        created_count = 0
        for day in range(6):  # Monday to Saturday
            try:
                timetable, created = Timetable.objects.get_or_create(
                    class_level=class_level,
                    day_of_week=day,
                    academic_year=academic_year,
                    term=term,
                    defaults={
                        'created_by': request.user,
                        'is_active': True
                    }
                )
                if created:
                    created_count += 1
            except Exception as e:
                messages.error(request, f'Error creating timetable: {str(e)}')
                return redirect('timetable_list')
        
        messages.success(request, f'Created {created_count} weekly timetables for {class_level}')
        return redirect('timetable_list')
    
    return redirect('timetable_list')

@login_required
def timetable_dashboard(request):
    """Timetable dashboard with quick access based on user role"""
    if is_admin(request.user):
        context = {
            'total_timetables': Timetable.objects.count(),
            'active_timetables': Timetable.objects.filter(is_active=True).count(),
            'upcoming_entries': TimetableEntry.objects.filter(
                timetable__is_active=True
            ).count(),
        }
        template = 'core/timetable/admin/dashboard.html'
    
    elif is_teacher(request.user):
        teacher = request.user.teacher
        assigned_classes = ClassAssignment.objects.filter(
            teacher=teacher
        ).values_list('class_level', flat=True).distinct()
        
        context = {
            'assigned_classes': assigned_classes,
            'class_count': len(assigned_classes),
            'today_schedule': get_teacher_schedule_today(teacher),
        }
        template = 'core/timetable/teacher/dashboard.html'
    
    elif is_student(request.user):
        student = request.user.student
        context = {
            'student': student,
            'today_schedule': get_student_schedule_today(student),
        }
        template = 'core/timetable/student/dashboard.html'
    
    else:
        return redirect('home')
    
    return render(request, template, context)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_teacher_schedule_today(teacher):
    """Get teacher's schedule for today"""
    today = timezone.now().date()
    day_of_week = today.weekday()  # Monday=0, Sunday=6
    
    # Adjust for Sunday (6) if needed
    if day_of_week == 6:  # Sunday
        return []
    
    # Get current academic year and term
    current_year = timezone.now().year
    next_year = current_year + 1
    academic_year = f"{current_year}/{next_year}"
    
    current_term = AcademicTerm.objects.filter(is_active=True).first()
    term = current_term.term if current_term else 1
    
    # Get today's entries for this teacher
    entries = TimetableEntry.objects.filter(
        teacher=teacher,
        timetable__day_of_week=day_of_week,
        timetable__academic_year=academic_year,
        timetable__term=term,
        timetable__is_active=True,
        is_break=False
    ).select_related(
        'timetable', 'subject', 'time_slot'
    ).order_by('time_slot__period_number')
    
    return entries

def get_student_schedule_today(student):
    """Get student's schedule for today"""
    today = timezone.now().date()
    day_of_week = today.weekday()  # Monday=0, Sunday=6
    
    # Adjust for Sunday (6) if needed
    if day_of_week == 6:  # Sunday
        return []
    
    # Get current academic year and term
    current_year = timezone.now().year
    next_year = current_year + 1
    academic_year = f"{current_year}/{next_year}"
    
    current_term = AcademicTerm.objects.filter(is_active=True).first()
    term = current_term.term if current_term else 1
    
    # Get today's timetable for student's class
    try:
        timetable = Timetable.objects.get(
            class_level=student.class_level,
            day_of_week=day_of_week,
            academic_year=academic_year,
            term=term,
            is_active=True
        )
        entries = timetable.entries.select_related(
            'time_slot', 'subject', 'teacher'
        ).order_by('time_slot__period_number')
        return entries
    except Timetable.DoesNotExist:
        return []

# ============================================================================
# PRINT VIEWS
# ============================================================================

@login_required
def print_timetable(request, pk):
    """Print-friendly version of timetable"""
    timetable = get_object_or_404(Timetable, pk=pk)
    
    # Check permissions
    if is_admin(request.user):
        pass
    elif is_teacher(request.user):
        if not ClassAssignment.objects.filter(
            class_level=timetable.class_level,
            teacher=request.user.teacher
        ).exists():
            raise PermissionDenied
    elif is_student(request.user):
        if timetable.class_level != request.user.student.class_level:
            raise PermissionDenied
    elif is_parent(request.user):
        children_classes = request.user.parentguardian.student.all().values_list('class_level', flat=True)
        if timetable.class_level not in children_classes:
            raise PermissionDenied
    else:
        raise PermissionDenied
    
    entries = timetable.entries.select_related('time_slot', 'subject', 'teacher')
    
    context = {
        'timetable': timetable,
        'entries': entries,
        'print_mode': True,
    }
    
    return render(request, 'core/timetable/print/timetable_print.html', context)

@login_required
def print_weekly_timetable(request):
    """Print weekly timetable for current user"""
    if is_student(request.user):
        student = request.user.student
        return print_student_weekly_timetable(request, student)
    elif is_teacher(request.user):
        teacher = request.user.teacher
        return print_teacher_weekly_schedule(request, teacher)
    else:
        raise PermissionDenied

def print_student_weekly_timetable(request, student):
    """Print student's weekly timetable"""
    # Get current academic year and term
    current_year = timezone.now().year
    next_year = current_year + 1
    academic_year = f"{current_year}/{next_year}"
    
    current_term = AcademicTerm.objects.filter(is_active=True).first()
    term = current_term.term if current_term else 1
    
    # Get weekly timetables
    timetables = Timetable.objects.filter(
        class_level=student.class_level,
        academic_year=academic_year,
        term=term,
        is_active=True
    ).prefetch_related(
        'entries__time_slot',
        'entries__subject',
        'entries__teacher'
    ).order_by('day_of_week')
    
    # Organize by day
    weekly_timetable = {}
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    for day_num, day_name in enumerate(days_order):
        try:
            timetable = timetables.get(day_of_week=day_num)
            weekly_timetable[day_name] = timetable.entries.all()
        except Timetable.DoesNotExist:
            weekly_timetable[day_name] = []
    
    context = {
        'student': student,
        'weekly_timetable': weekly_timetable,
        'days_order': days_order,
        'academic_year': academic_year,
        'term': term,
        'print_mode': True,
    }
    
    return render(request, 'core/timetable/print/weekly_timetable_print.html', context)

def print_teacher_weekly_schedule(request, teacher):
    """Print teacher's weekly schedule"""
    # Get current academic year and term
    current_year = timezone.now().year
    next_year = current_year + 1
    academic_year = f"{current_year}/{next_year}"
    
    current_term = AcademicTerm.objects.filter(is_active=True).first()
    term = current_term.term if current_term else 1
    
    # Get teacher's weekly schedule
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    schedule_by_day = {}
    
    for day_num, day_name in enumerate(days_order):
        entries = TimetableEntry.objects.filter(
            teacher=teacher,
            timetable__day_of_week=day_num,
            timetable__academic_year=academic_year,
            timetable__term=term,
            timetable__is_active=True,
            is_break=False
        ).select_related(
            'timetable', 'subject', 'time_slot'
        ).order_by('time_slot__period_number')
        
        schedule_by_day[day_name] = entries
    
    context = {
        'teacher': teacher,
        'schedule_by_day': schedule_by_day,
        'days_order': days_order,
        'academic_year': academic_year,
        'term': term,
        'print_mode': True,
    }
    
    return render(request, 'core/timetable/print/teacher_schedule_print.html', context)