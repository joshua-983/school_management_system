"""
Analytics and reporting models.
"""
import logging
from django.db import models
from django.utils import timezone
from django.db.models import Avg, Sum, Count

from core.models.base import CLASS_LEVEL_CHOICES
from core.models.academic import Subject
from core.models.student import Student

logger = logging.getLogger(__name__)


class AnalyticsCache(models.Model):
    """Cache for pre-computed analytics data"""
    name = models.CharField(max_length=100, unique=True)
    data = models.JSONField()
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Analytics Cache'
        verbose_name_plural = 'Analytics Caches'
    
    @classmethod
    def get_cached_data(cls, name, default=None):
        try:
            return cls.objects.get(name=name).data
        except cls.DoesNotExist:
            return default or {}


class GradeAnalytics(models.Model):
    """Model to store grade-related analytics"""
    class_level = models.CharField(max_length=20, choices=CLASS_LEVEL_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    average_score = models.FloatField()
    highest_score = models.FloatField()
    lowest_score = models.FloatField()
    date_calculated = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('class_level', 'subject', 'date_calculated')
        verbose_name = 'Grade Analytics'
        verbose_name_plural = 'Grade Analytics'


class AttendanceAnalytics(models.Model):
    """Model to store attendance analytics"""
    class_level = models.CharField(max_length=20, choices=CLASS_LEVEL_CHOICES)
    date = models.DateField()
    present_count = models.IntegerField()
    absent_count = models.IntegerField()
    late_count = models.IntegerField()
    attendance_rate = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('class_level', 'date')
        verbose_name = 'Attendance Analytics'
        verbose_name_plural = 'Attendance Analytics'


class Holiday(models.Model):
    """Model to store school holidays"""
    name = models.CharField(max_length=200)
    date = models.DateField()
    is_school_holiday = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Holiday"
        verbose_name_plural = "Holidays"
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.name} ({self.date})"
