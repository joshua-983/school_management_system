# core/models/report_card.py
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone

class ReportCard(models.Model):
    TERM_CHOICES = [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ]
    
    GRADE_CHOICES = [
        ('A+', 'A+ (90-100)'),
        ('A', 'A (80-89)'),
        ('B+', 'B+ (70-79)'),
        ('B', 'B (60-69)'),
        ('C+', 'C+ (50-59)'),
        ('C', 'C (40-49)'),
        ('D+', 'D+ (30-39)'),
        ('D', 'D (20-29)'),
        ('E', 'E (0-19)'),
    ]
    
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='report_cards')
    academic_year = models.CharField(
        max_length=9, 
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Format: YYYY/YYYY')]
    )
    term = models.PositiveSmallIntegerField(
        choices=TERM_CHOICES, 
        validators=[MinValueValidator(1), MaxValueValidator(3)]
    )
    average_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Average score across all subjects"
    )
    overall_grade = models.CharField(
        max_length=2, 
        choices=GRADE_CHOICES, 
        blank=True,
        help_text="Overall grade based on average score"
    )
    is_published = models.BooleanField(default=False)
    teacher_remarks = models.TextField(blank=True, help_text="Comments from class teacher")
    principal_remarks = models.TextField(blank=True, help_text="Comments from principal")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_report_cards'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'academic_year', 'term')
        ordering = ['-academic_year', '-term', 'student__last_name']
        verbose_name = 'Report Card'
        verbose_name_plural = 'Report Cards'
        indexes = [
            models.Index(fields=['student', 'academic_year', 'term']),
            models.Index(fields=['is_published']),
            models.Index(fields=['average_score']),
        ]
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.academic_year} Term {self.term}"
    
    def save(self, *args, **kwargs):
        """Calculate grades if not already calculated"""
        is_new = self.pk is None
        
        # If average score is not set or report card is new, calculate grades
        if is_new or not self.average_score:
            self.calculate_grades()
        
        super().save(*args, **kwargs)
        
        # For new report cards, also create/update related objects
        if is_new:
            self.update_related_data()
    
    def calculate_grades(self):
        """Calculate average score and overall grade from student's grades"""
        grades = Grade.objects.filter(
            student=self.student,
            academic_year=self.academic_year,
            term=self.term
        )
    
        if grades.exists():
            # Calculate average of total scores
            total_scores = [grade.total_score for grade in grades if grade.total_score is not None]
            if total_scores:
                self.average_score = sum(total_scores) / len(total_scores)
                # Use SchoolConfiguration for grade calculation
                from core.models.configuration import SchoolConfiguration
                config = SchoolConfiguration.get_config()
                self.overall_grade = config.get_letter_grade_for_score(self.average_score)
            else:
                self.average_score = Decimal('0.00')
                self.overall_grade = ''
        else:
            self.average_score = Decimal('0.00')
            self.overall_grade = ''
    
    @staticmethod
    def calculate_grade(score):
        """Calculate letter grade based on score"""
        if score is None:
            return ''
            
        score = float(score)
        if score >= 90: return 'A+'
        elif score >= 80: return 'A'
        elif score >= 70: return 'B+'
        elif score >= 60: return 'B'
        elif score >= 50: return 'C+'
        elif score >= 40: return 'C'
        elif score >= 30: return 'D+'
        elif score >= 20: return 'D'
        else: return 'E'
    
    def get_absolute_url(self):
        """Get URL for viewing this report card"""
        return reverse('report_card_detail', kwargs={
            'student_id': self.student.id,
            'report_card_id': self.id
        })
    
    def get_pdf_url(self):
        """Get URL for PDF version"""
        return reverse('report_card_pdf_detail', kwargs={
            'student_id': self.student.id,
            'report_card_id': self.id
        })
    
    def get_edit_url(self):
        """Get URL for editing grades"""
        return reverse('grade_edit', kwargs={'pk': self.id})
    
    def can_user_access(self, user):
        """Check if user has permission to view this report card"""
        # Import here to avoid circular imports
        from django.contrib.auth.models import User
        
        if user.is_superuser or user.is_staff:
            return True
        
        if hasattr(user, 'student') and user.student == self.student:
            return True
        
        if hasattr(user, 'teacher'):
            from .academic import ClassAssignment
            return ClassAssignment.objects.filter(
                class_level=self.student.class_level,
                teacher=user.teacher
            ).exists()
        
        if hasattr(user, 'parentguardian'):
            return self.student in user.parentguardian.students.all()
        
        return False
    
    def get_performance_level(self):
        """Get performance level description"""
        score = float(self.average_score)
        if score >= 80:
            return 'Excellent'
        elif score >= 70:
            return 'Very Good'
        elif score >= 60:
            return 'Good'
        elif score >= 50:
            return 'Average'
        elif score >= 40:
            return 'Below Average'
        elif score >= 30:
            return 'Poor'
        else:
            return 'Very Poor'
    
    def get_grade_color(self):
        """Get Bootstrap color class for grade"""
        grade = self.overall_grade
        if grade in ['A+', 'A']:
            return 'success'
        elif grade in ['B+', 'B']:
            return 'info'
        elif grade in ['C+', 'C']:
            return 'warning'
        elif grade in ['D+', 'D']:
            return 'warning'
        elif grade == 'E':
            return 'danger'
        else:
            return 'secondary'
    
    def publish(self, user=None):
        """Publish the report card"""
        self.is_published = True
        if user:
            self.updated_by = user
        self.save()
        return self
    
    def unpublish(self, user=None):
        """Unpublish the report card"""
        self.is_published = False
        if user:
            self.updated_by = user
        self.save()
        return self
    
    def update_related_data(self):
        """Update related analytics or cache data"""
        # You can add logic here to update analytics cache, etc.
        pass
    
    def get_grades_summary(self):
        """Get summary of all grades for this report card"""
        from .grades import Grade
        
        grades = Grade.objects.filter(
            student=self.student,
            academic_year=self.academic_year,
            term=self.term
        ).select_related('subject')
        
        return {
            'total_subjects': grades.count(),
            'grades_list': [
                {
                    'subject': grade.subject.name,
                    'score': grade.total_score,
                    'grade': grade.letter_grade,
                    'teacher': grade.teacher.get_full_name() if grade.teacher else 'N/A'
                }
                for grade in grades
            ]
        }
    
    @classmethod
    def get_for_student(cls, student, academic_year=None, term=None):
        """Get report cards for a student, optionally filtered by year and term"""
        queryset = cls.objects.filter(student=student)
        
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        
        if term:
            queryset = queryset.filter(term=term)
        
        return queryset.order_by('-academic_year', '-term')
    
    @classmethod
    def generate_report_card(cls, student, academic_year, term, user=None):
        """Generate a new report card for a student"""
        # Check if report card already exists
        existing = cls.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        ).first()
        
        if existing:
            return existing
        
        # Create new report card
        report_card = cls.objects.create(
            student=student,
            academic_year=academic_year,
            term=term,
            created_by=user
        )
        
        # Calculate grades
        report_card.calculate_grades()
        report_card.save()
        
        return report_card
    
    @property
    def academic_year_display(self):
        """Get formatted academic year"""
        return self.academic_year.replace('/', ' - ')
    
    @property
    def term_display(self):
        """Get formatted term"""
        return f"Term {self.term}"
    
    @property
    def status_badge(self):
        """Get status badge HTML"""
        if self.is_published:
            return '<span class="badge bg-success">Published</span>'
        else:
            return '<span class="badge bg-warning">Draft</span>'