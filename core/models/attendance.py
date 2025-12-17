"""
Attendance management models.
"""
import logging
from datetime import date
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q

from core.models.base import GhanaEducationMixin
from core.models.academic import AcademicTerm
from core.models.student import Student

logger = logging.getLogger(__name__)


class AttendancePeriod(models.Model):
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom'),
    ]
    
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    name = models.CharField(max_length=100, blank=True, help_text="Custom name for the period")
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE, related_name='attendance_periods')
    start_date = models.DateField()
    end_date = models.DateField()
    is_locked = models.BooleanField(default=False, help_text="Lock period to prevent modifications")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('period_type', 'term', 'start_date')
        ordering = ['-start_date']
        verbose_name = 'Attendance Period'
        verbose_name_plural = 'Attendance Periods'
    
    def __str__(self):
        if self.name:
            return f"{self.name} ({self.start_date} to {self.end_date})"
        return f"{self.get_period_type_display()} ({self.start_date} to {self.end_date})"
    
    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("End date must be after start date")
        
        if (self.start_date < self.term.start_date or 
            self.end_date > self.term.end_date):
            raise ValidationError("Period must be within term dates")
        
        overlapping = AttendancePeriod.objects.filter(
            period_type=self.period_type,
            term=self.term,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(pk=self.pk)
        
        if overlapping.exists():
            raise ValidationError("This period overlaps with an existing period")
    
    def get_total_school_days(self):
        """Calculate total school days in the period"""
        total_days = 0
        current_date = self.start_date
        
        while current_date <= self.end_date:
            if current_date.weekday() < 5:
                total_days += 1
            current_date += timedelta(days=1)
        
        return total_days


class StudentAttendance(models.Model, GhanaEducationMixin):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
        ('sick', 'Sick'),
        ('other', 'Other'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    period = models.ForeignKey(AttendancePeriod, on_delete=models.CASCADE, null=True, blank=True)
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Recorded By'
    )
    notes = models.TextField(blank=True, help_text="Additional notes about attendance")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'date', 'period')
        ordering = ['-date', 'student__last_name']
        verbose_name = 'Student Attendance'
        verbose_name_plural = 'Student Attendances'
        indexes = [
            models.Index(fields=['student', 'date']),
            models.Index(fields=['date', 'status']),
            models.Index(fields=['term', 'student']),
        ]
    
    def __str__(self):
        return f"{self.student} - {self.date} - {self.get_status_display()}"
    
    def clean(self):
        if not (self.term.start_date <= self.date <= self.term.end_date):
            raise ValidationError("Date must be within the term dates")
        
        if self.period and not (self.period.start_date <= self.date <= self.period.end_date):
            raise ValidationError("Date must be within the period dates")
        
        if self.period and self.period.is_locked:
            if self.pk is None:
                raise ValidationError("Cannot create attendance for a locked period")
            else:
                original = StudentAttendance.objects.get(pk=self.pk)
                if original.period != self.period or original.date != self.date:
                    raise ValidationError("Cannot modify attendance for a locked period")
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_attendance_summary()
    
    def update_attendance_summary(self):
        """Update attendance summary for this student and term"""
        # Update term summary
        term_summary, created = AttendanceSummary.objects.get_or_create(
            student=self.student,
            term=self.term,
            period=None
        )
        term_summary.calculate_summary()
        
        # Update period summary if period exists
        if self.period:
            period_summary, created = AttendanceSummary.objects.get_or_create(
                student=self.student,
                term=self.term,
                period=self.period
            )
            period_summary.calculate_summary()
    
    def is_ghana_school_day(self):
        """Check if the attendance date is a valid Ghana school day"""
        if self.date.weekday() >= 5:
            return False
        
        ghana_holidays = [
            date(self.date.year, 1, 1),
            date(self.date.year, 3, 6),
            date(self.date.year, 5, 1),
            date(self.date.year, 7, 1),
            date(self.date.year, 12, 25),
            date(self.date.year, 12, 26),
        ]
        
        return self.date not in ghana_holidays
    
    @property
    def is_present(self):
        """Check if student is considered present (includes late and excused)"""
        return self.status in ['present', 'late', 'excused']


class AttendanceSummary(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_summaries')
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE)
    period = models.ForeignKey(AttendancePeriod, on_delete=models.CASCADE, null=True, blank=True)
    
    # Counts
    days_present = models.PositiveIntegerField(default=0)
    days_absent = models.PositiveIntegerField(default=0)
    days_late = models.PositiveIntegerField(default=0)
    days_excused = models.PositiveIntegerField(default=0)
    days_sick = models.PositiveIntegerField(default=0)
    days_other = models.PositiveIntegerField(default=0)
    
    # Calculated fields
    total_days = models.PositiveIntegerField(default=0)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    present_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'term', 'period')
        verbose_name_plural = 'Attendance Summaries'
        ordering = ['student__last_name', 'student__first_name']
    
    def __str__(self):
        period_name = self.period.name if self.period else 'Term'
        return f"{self.student} - {period_name} - {self.attendance_rate}%"
    
    def calculate_summary(self):
        """Calculate and update attendance summary"""
        filters = {
            'student': self.student,
            'term': self.term,
        }
        
        if self.period:
            filters['period'] = self.period
            attendance_records = StudentAttendance.objects.filter(
                **filters,
                date__range=[self.period.start_date, self.period.end_date]
            )
        else:
            attendance_records = StudentAttendance.objects.filter(
                **filters,
                date__range=[self.term.start_date, self.term.end_date]
            )
        
        # Count by status
        self.days_present = attendance_records.filter(status='present').count()
        self.days_absent = attendance_records.filter(status='absent').count()
        self.days_late = attendance_records.filter(status='late').count()
        self.days_excused = attendance_records.filter(status='excused').count()
        self.days_sick = attendance_records.filter(status='sick').count()
        self.days_other = attendance_records.filter(status='other').count()
        
        # Calculate totals and rates
        self.total_days = attendance_records.count()
        
        if self.total_days > 0:
            present_days = self.days_present + self.days_late + self.days_excused
            self.present_rate = (present_days / self.total_days) * 100
            self.attendance_rate = (self.days_present / self.total_days) * 100
        
        self.save()
    
    def get_ges_compliance(self):
        """Check if attendance meets Ghana Education Service requirements (80% minimum)"""
        return self.present_rate >= 80.0
    
    def get_status_display(self):
        """Get display status for the summary"""
        if self.present_rate >= 90:
            return "Excellent"
        elif self.present_rate >= 80:
            return "Good"
        elif self.present_rate >= 70:
            return "Fair"
        else:
            return "Poor"