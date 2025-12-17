"""
Academic models: Subject, AcademicTerm, ClassAssignment
"""
import re
import logging
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta, date

from core.models.base import (
    CLASS_LEVEL_CHOICES,
    TERM_CHOICES,
    GhanaEducationMixin
)

logger = logging.getLogger(__name__)


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True, editable=False)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'

    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def get_assignment_count(self):
        """Get number of assignments for this subject"""
        from core.models.assignments import Assignment
        return Assignment.objects.filter(subject=self, is_active=True).count()
    
    def generate_subject_code(self):
        """Generate a 3-letter subject code from the name"""
        # Remove common words and get first letters
        common_words = ['and', 'the', 'of', 'for', 'in', 'with', 'to', 'on', 'at', 'from', 'by', 'about', 'as', 'into', 'like', 'through', 'after', 'over', 'between', 'out', 'against', 'during', 'without', 'before', 'under', 'around', 'among']
        
        words = self.name.upper().split()
        meaningful_words = [word for word in words if word.lower() not in common_words]
        
        if meaningful_words:
            # If single word, take first 3 letters
            if len(meaningful_words) == 1:
                code = meaningful_words[0][:3]
            else:
                # If multiple words, take first letter of each (max 3)
                code = ''.join(word[0] for word in meaningful_words[:3])
        else:
            # Fallback: take first 3 letters of first word
            code = words[0][:3] if words else 'SUB'
        
        # Ensure code is exactly 3 characters
        code = code.ljust(3, 'X')[:3]
        
        # Make unique if code already exists
        base_code = code
        counter = 1
        while Subject.objects.filter(code=code).exclude(pk=self.pk).exists():
            code = f"{base_code}{counter}"
            counter += 1
        
        return code
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_subject_code()
        super().save(*args, **kwargs)


class AcademicTerm(models.Model, GhanaEducationMixin):
    TERM_CHOICES = TERM_CHOICES
    
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('term', 'academic_year')
        ordering = ['-academic_year', 'term']
        verbose_name = 'Academic Term'
        verbose_name_plural = 'Academic Terms'
    
    def __str__(self):
        return f"{self.get_term_display()} {self.academic_year}"
    
    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("End date must be after start date")
        
        # Ensure term duration is reasonable (3-4 months)
        if (self.end_date - self.start_date).days > 150:
            raise ValidationError("Term duration should not exceed 5 months")
        
        # Ensure only one active term per academic year
        if self.is_active:
            AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
    
    def get_total_school_days(self):
        """Calculate total school days in the term"""
        total_days = 0
        current_date = self.start_date
        
        while current_date <= self.end_date:
            if current_date.weekday() < 5:  # Monday to Friday
                total_days += 1
            current_date += timedelta(days=1)
        
        return total_days
    
    def get_progress_percentage(self):
        """Get term progress percentage"""
        today = timezone.now().date()
        if today < self.start_date:
            return 0
        elif today > self.end_date:
            return 100
        
        total_days = (self.end_date - self.start_date).days
        days_passed = (today - self.start_date).days
        return min(100, round((days_passed / total_days) * 100, 1))
    
    def get_remaining_days(self):
        """Get remaining days in term"""
        today = timezone.now().date()
        if today > self.end_date:
            return 0
        return (self.end_date - today).days


class ClassAssignment(models.Model):
    class_level = models.CharField(max_length=2, choices=CLASS_LEVEL_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('class_level', 'subject', 'academic_year')
        verbose_name = 'Class Assignment'
        verbose_name_plural = 'Class Assignments'
        ordering = ['class_level', 'subject']
        indexes = [
            models.Index(fields=['class_level', 'subject', 'academic_year']),
            models.Index(fields=['teacher', 'is_active']),
            models.Index(fields=['is_active', 'academic_year']),
            models.Index(fields=['class_level', 'is_active']),
        ]

    def __str__(self):
        return f"{self.get_class_level_display()} - {self.subject} - {self.teacher} ({self.academic_year})"
    
    def get_students(self):
        """Get all students in this class"""
        from core.models.student import Student
        return Student.objects.filter(class_level=self.class_level, is_active=True)
    
    def get_students_count(self):
        """Get count of students in this class"""
        return self.get_students().count()