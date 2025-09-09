from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages

from .base_views import is_admin, is_teacher, is_student, is_parent
from ..models import TimeSlot, Timetable, TimetableEntry, Teacher, Subject, Student, ClassAssignment, AcademicTerm
from ..forms import TimeSlotForm, TimetableForm, TimetableEntryForm, TimetableFilterForm
from ..models import CLASS_LEVEL_CHOICES

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

class TimetableListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Timetable
    template_name = 'core/timetable/timetable_list.html'
    context_object_name = 'timetables'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
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
        
        # For teachers, only show timetables for classes they teach
        if is_teacher(self.request.user):
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            queryset = queryset.filter(class_level__in=teacher_classes)
        
        return queryset.order_by('class_level', 'day_of_week')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['class_levels'] = CLASS_LEVEL_CHOICES
        context['current_filters'] = {
            'class_level': self.request.GET.get('class_level', ''),
            'academic_year': self.request.GET.get('academic_year', ''),
            'term': self.request.GET.get('term', ''),
            'day_of_week': self.request.GET.get('day_of_week', ''),
        }
        return context

class TimetableCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Timetable
    form_class = TimetableForm
    template_name = 'core/timetable/timetable_form.html'
    
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
    template_name = 'core/timetable/timetable_detail.html'
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
        return context

class TimetableManageView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'core/timetable/timetable_manage.html'
    
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
            if entry_id:
                # Update existing entry
                entry = get_object_or_404(TimetableEntry, id=entry_id, timetable=timetable)
                form = TimetableEntryForm(request.POST, instance=entry, timetable=timetable)
            else:
                # Create new entry
                form = TimetableEntryForm(request.POST, timetable=timetable)
            
            if form.is_valid():
                entry = form.save(commit=False)
                entry.timetable = timetable
                entry.time_slot = timeslot
                entry.save()
        
        messages.success(request, 'Timetable updated successfully')
        return redirect('timetable_detail', pk=timetable.pk)

class TimetableDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Timetable
    template_name = 'core/timetable/timetable_confirm_delete.html'
    success_url = reverse_lazy('timetable_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Timetable deleted successfully')
        return super().delete(request, *args, **kwargs)

class StudentTimetableView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/timetable/student_timetable.html'
    
    def test_func(self):
        return is_student(self.request.user) or is_parent(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if is_student(self.request.user):
            student = self.request.user.student
            class_level = student.class_level
            context['student'] = student
        else:
            # For parents, get the first child's class level
            children = self.request.user.parentguardian.student.all()
            if children.exists():
                class_level = children.first().class_level
                context['student'] = children.first()
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
                    weekly_timetable[day_name] = timetable.entries.order_by('time_slot__period_number')
                except Timetable.DoesNotExist:
                    weekly_timetable[day_name] = None
            
            # Get all time slots for the weekly overview
            time_slots = TimeSlot.objects.order_by('period_number')
            time_slot_list = []
            
            for slot in time_slots:
                time_slot_list.append(f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}")
            
            context.update({
                'weekly_timetable': weekly_timetable,
                'time_slots': time_slot_list,
                'days_order': days_order,
                'class_level': class_level,
                'academic_year': academic_year,
                'term': term,
            })
        
        return context

class TeacherTimetableView(LoginRequiredMixin, TemplateView):
    template_name = 'core/timetable/teacher_timetable.html'
    
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
            timetable__is_active=True
        ).select_related(
            'timetable', 'subject', 'time_slot'
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
        time_slots = []
        for entry in entries:
            time_slot = f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}"
            if time_slot not in time_slots:
                time_slots.append(time_slot)
        
        context['time_slots'] = sorted(time_slots)
        
        return context

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