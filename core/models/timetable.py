"""
Timetable management models.
"""
from django.db import models
from django.contrib.auth import get_user_model

from core.models.base import CLASS_LEVEL_CHOICES
from core.models.academic import Subject, AcademicTerm
from core.models.teacher import Teacher

User = get_user_model()


class TimeSlot(models.Model):
    PERIOD_CHOICES = [
        (1, '1st Period (8:00-9:00)'),
        (2, '2nd Period (9:00-10:00)'),
        (3, '3rd Period (10:00-11:00)'),
        (4, '4th Period (11:00-12:00)'),
        (5, '5th Period (12:00-1:00)'),
        (6, '6th Period (1:00-2:00)'),
        (7, '7th Period (2:00-3:00)'),
        (8, '8th Period (3:00-4:00)'),
    ]
    
    period_number = models.PositiveSmallIntegerField(choices=PERIOD_CHOICES, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False)
    break_name = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['period_number']
        verbose_name = 'Time Slot'
        verbose_name_plural = 'Time Slots'
        permissions = [
            ('can_view_timeslot', 'Can view time slot'),
            ('manage_timeslot', 'Can manage time slot'),
        ]
    
    def __str__(self):
        if self.is_break:
            return f"{self.break_name} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"
        return f"Period {self.period_number} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"


class Timetable(models.Model):
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
    ]
    
    class_level = models.CharField(max_length=2, choices=CLASS_LEVEL_CHOICES)
    day_of_week = models.PositiveSmallIntegerField(choices=DAYS_OF_WEEK)
    academic_year = models.CharField(max_length=20)
    term = models.PositiveSmallIntegerField(choices=AcademicTerm.TERM_CHOICES)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('class_level', 'day_of_week', 'academic_year', 'term')
        ordering = ['class_level', 'day_of_week']
        verbose_name = 'Timetable'
        verbose_name_plural = 'Timetables'
        permissions = [
            ('can_view_timetable', 'Can view timetable'),
            ('manage_timetable', 'Can manage timetable'),
        ]
    
    def __str__(self):
        return f"{self.get_class_level_display()} - {self.get_day_of_week_display()} - {self.academic_year} Term {self.term}"


class TimetableEntry(models.Model):
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='entries')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    classroom = models.CharField(max_length=100, blank=True)
    is_break = models.BooleanField(default=False)
    break_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['time_slot__period_number']
        unique_together = ('timetable', 'time_slot')
        verbose_name = 'Timetable Entry'
        verbose_name_plural = 'Timetable Entries'
        permissions = [
            ('view_timetable_entry', 'Can view timetable entry'),
            ('manage_timetable_entry', 'Can manage timetable entry'),
        ]
    
    def __str__(self):
        if self.is_break:
            return f"{self.break_name} - Break"
        return f"{self.time_slot} - {self.subject.name} - {self.teacher.get_full_name()}"