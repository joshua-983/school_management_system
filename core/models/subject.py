# core/models/subject.py
"""
Subject Model
Standalone subject management
"""
import re
import logging
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class Subject(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="Subject Name"
    )
    code = models.CharField(
        max_length=10, 
        unique=True, 
        editable=False,
        verbose_name="Subject Code"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]

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
    
    def get_grades_for_year_term(self, academic_year, term):
        """Get grades for this subject in specific year/term"""
        from core.models.grades import Grade
        return Grade.objects.filter(
            subject=self,
            academic_year=academic_year,
            term=term
        )
    
    def get_class_assignments(self):
        """Get class assignments for this subject"""
        from core.models.class_assignment import ClassAssignment
        return ClassAssignment.objects.filter(
            subject=self,
            is_active=True
        )
    
    def get_average_score(self, academic_year=None, term=None):
        """Get average score for this subject"""
        from core.models.grades import Grade
        queryset = Grade.objects.filter(subject=self)
        
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        if term:
            queryset = queryset.filter(term=term)
        
        avg = queryset.aggregate(models.Avg('total_score'))['total_score__avg']
        return avg if avg else 0
    
    def is_being_used(self):
        """Check if subject is being used in any grades"""
        from core.models.grades import Grade
        return Grade.objects.filter(subject=self).exists()
    
    def deactivate(self):
        """Deactivate subject"""
        self.is_active = False
        self.save()
        return True
    
    def activate(self):
        """Activate subject"""
        self.is_active = True
        self.save()
        return True


# Export
__all__ = ['Subject']