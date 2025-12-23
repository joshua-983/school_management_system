# core/models/grades.py - UPDATED
import re
import logging
from decimal import Decimal, InvalidOperation
from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from django.db.models import Avg, Sum
from datetime import date

from core.models.base import CLASS_LEVEL_CHOICES, TERM_CHOICES
from core.models.academic import Subject, ClassAssignment, AcademicTerm
from core.models.student import Student
from core.models.configuration import SchoolConfiguration

logger = logging.getLogger(__name__)
User = get_user_model()

class Grade(models.Model):
    """
    Professional Grade Model - Stores RAW PERCENTAGES (0-100%)
    Uses SchoolConfiguration for weights and grading
    """
    
    # GES Grade Choices with detailed descriptions
    GES_GRADE_CHOICES = [
        ('1', '1 (90-100%) - Outstanding'),
        ('2', '2 (80-89%) - Excellent'), 
        ('3', '3 (70-79%) - Very Good'),
        ('4', '4 (60-69%) - Good'),
        ('5', '5 (50-59%) - Satisfactory'),
        ('6', '6 (40-49%) - Fair'),
        ('7', '7 (30-39%) - Weak'),
        ('8', '8 (20-29%) - Very Weak'),
        ('9', '9 (0-19%) - Fail'),
        ('N/A', 'Not Available'),
    ]

    # Letter Grade Choices
    LETTER_GRADE_CHOICES = [
        ('A+', 'A+ (90-100%) - Outstanding'),
        ('A', 'A (80-89%) - Excellent'),
        ('B+', 'B+ (70-79%) - Very Good'),
        ('B', 'B (60-69%) - Good'),
        ('C+', 'C+ (50-59%) - Satisfactory'),
        ('C', 'C (40-49%) - Fair'),
        ('D+', 'D+ (30-39%) - Weak'),
        ('D', 'D (20-29%) - Very Weak'),
        ('F', 'F (0-19%) - Fail'),
        ('N/A', 'Not Available'),
    ]

    # ========== MODEL FIELDS ==========
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='grades')
    class_assignment = models.ForeignKey(
        ClassAssignment, 
        on_delete=models.CASCADE, 
        related_name='grades',
        null=True,
        blank=True
    )
    academic_year = models.CharField(
        max_length=9, 
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Academic year must be in format YYYY/YYYY')]
    )
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)

    # ========== RAW PERCENTAGE SCORES (0-100%) ==========
    # These fields store the raw percentage scores (e.g., 75.5%)
    homework_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(Decimal('100.00'), 'Score cannot exceed 100%')
        ],
        verbose_name="Homework Score (%)",
        default=Decimal('0.00'),
        help_text="Homework percentage score (0-100%)"
    )
    
    classwork_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(Decimal('100.00'), 'Score cannot exceed 100%')
        ],
        verbose_name="Classwork Score (%)",
        default=Decimal('0.00'),
        help_text="Classwork percentage score (0-100%)"
    )
    
    test_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(Decimal('100.00'), 'Score cannot exceed 100%')
        ],
        verbose_name="Test Score (%)", 
        default=Decimal('0.00'),
        help_text="Test percentage score (0-100%)"
    )
    
    exam_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(Decimal('100.00'), 'Score cannot exceed 100%')
        ],
        verbose_name="Exam Score (%)",
        default=Decimal('0.00'),
        help_text="Exam percentage score (0-100%)"
    )

    # ========== CALCULATED FIELDS ==========
    total_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        editable=False, 
        null=True, 
        blank=True,
        verbose_name="Total Score (%)",
        help_text="Automatically calculated weighted total score"
    )
    
    ges_grade = models.CharField(
        max_length=3, 
        choices=GES_GRADE_CHOICES, 
        editable=False, 
        default='N/A',
        verbose_name="GES Grade",
        help_text="Automatically determined GES grade"
    )
    
    letter_grade = models.CharField(
        max_length=3,
        choices=LETTER_GRADE_CHOICES,
        editable=False,
        blank=True,
        null=True,
        verbose_name="Letter Grade",
        help_text="Automatically determined letter grade"
    )
    
    remarks = models.TextField(
        blank=True,
        verbose_name="Teacher Remarks",
        help_text="Additional comments or notes about the grade"
    )
    
    # Class level field to help with class assignment creation
    class_level = models.CharField(
        max_length=2,
        choices=CLASS_LEVEL_CHOICES,
        blank=True,
        null=True,
        verbose_name="Class Level",
        help_text="Student's class level (auto-set from student)"
    )
    
    # ========== AUDIT FIELDS ==========
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="Recorded By",
        help_text="User who recorded this grade"
    )
    
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Last Updated"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    
    # Status fields
    is_locked = models.BooleanField(
        default=False,
        verbose_name="Is Locked",
        help_text="Prevent further modifications to this grade"
    )
    
    requires_review = models.BooleanField(
        default=False,
        verbose_name="Requires Review",
        help_text="Flag for administrative review"
    )
    
    review_notes = models.TextField(
        blank=True,
        verbose_name="Review Notes",
        help_text="Notes from administrative review"
    )

    class Meta:
        unique_together = ('student', 'subject', 'academic_year', 'term')
        ordering = ['academic_year', 'term', 'student__last_name', 'subject__name']
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'
        indexes = [
            models.Index(fields=['student', 'academic_year', 'term']),
            models.Index(fields=['subject', 'academic_year', 'term']),
            models.Index(fields=['total_score']),
        ]
    
    def __str__(self):
        try:
            student_name = self.student.get_full_name() if self.student else f"Student {self.student_id}"
            subject_name = self.subject.name if self.subject else f"Subject {self.subject_id}"
            return f"{student_name} - {subject_name}: {self.total_score or 0}%"
        except Exception:
            return f"Grade {self.pk or 'new'}"
    
    def clean(self):
        """Validate grade data"""
        errors = {}
        
        # Validate scores are between 0-100%
        percentage_fields = [
            'homework_percentage',
            'classwork_percentage', 
            'test_percentage',
            'exam_percentage'
        ]
        
        for field_name in percentage_fields:
            score = getattr(self, field_name, Decimal('0.00'))
            if score is None:
                continue
                
            try:
                score_decimal = Decimal(str(score))
                if score_decimal < Decimal('0.00'):
                    errors[field_name] = 'Score cannot be negative'
                elif score_decimal > Decimal('100.00'):
                    errors[field_name] = 'Score cannot exceed 100%'
            except (InvalidOperation, TypeError, ValueError):
                errors[field_name] = 'Invalid score format'
        
        # Validate academic year format
        if self.academic_year and not re.match(r'^\d{4}/\d{4}$', self.academic_year):
            errors['academic_year'] = 'Academic year must be in format YYYY/YYYY'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Save with automatic calculations"""
        try:
            # Set class_level from student if not set
            if self.student and not self.class_level:
                self.class_level = self.student.class_level
            
            # Auto-create class_assignment if needed
            if not self.class_assignment_id and self.student and self.subject and self.academic_year:
                try:
                    self.class_assignment = self.get_or_create_class_assignment()
                except Exception as e:
                    logger.warning(f"Could not auto-create class assignment: {e}")
            
            # Validate
            self.full_clean()
            
            # Calculate total score and grades
            self.calculate_total_score()
            self.determine_grades()
            
            super().save(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error saving grade: {str(e)}", exc_info=True)
            raise
    
    def calculate_total_score(self):
        """Calculate weighted total score using SchoolConfiguration weights"""
        try:
            config = SchoolConfiguration.get_config()
            
            # Get weights (these are already percentages, e.g., 20, 30, 10, 40)
            homework_weight = config.homework_weight / Decimal('100.00')  # 20% → 0.20
            classwork_weight = config.classwork_weight / Decimal('100.00')  # 30% → 0.30
            test_weight = config.test_weight / Decimal('100.00')  # 10% → 0.10
            exam_weight = config.exam_weight / Decimal('100.00')  # 40% → 0.40
            
            # Convert percentage scores to decimal (e.g., 75% → 0.75)
            homework_score = (self.homework_percentage or Decimal('0.00')) / Decimal('100.00')
            classwork_score = (self.classwork_percentage or Decimal('0.00')) / Decimal('100.00')
            test_score = (self.test_percentage or Decimal('0.00')) / Decimal('100.00')
            exam_score = (self.exam_percentage or Decimal('0.00')) / Decimal('100.00')
            
            # Calculate weighted total (returns percentage)
            total = (
                (homework_score * homework_weight) +
                (classwork_score * classwork_weight) +
                (test_score * test_weight) +
                (exam_score * exam_weight)
            ) * Decimal('100.00')
            
            self.total_score = total.quantize(Decimal('0.01'))
            
            logger.debug(f"Total calculated: {self.total_score}%")
            
        except Exception as e:
            logger.error(f"Error calculating total score: {str(e)}", exc_info=True)
            self.total_score = None
    
    def determine_grades(self):
        """Determine grades using SchoolConfiguration"""
        try:
            if self.total_score is None:
                self.ges_grade = 'N/A'
                self.letter_grade = 'N/A'
                return

            config = SchoolConfiguration.get_config()
            
            self.ges_grade = config.get_ges_grade_for_score(self.total_score)
            self.letter_grade = config.get_letter_grade_for_score(self.total_score)
            
            logger.debug(f"Grades determined - GES: {self.ges_grade}, Letter: {self.letter_grade}")
            
        except Exception as e:
            logger.error(f"Error determining grades: {str(e)}")
            self.ges_grade = 'N/A'
            self.letter_grade = 'N/A'
    
    # ========== HELPER METHODS ==========
    
    def get_weighted_contributions(self):
        """Get weighted contributions for display - used in templates"""
        try:
            config = SchoolConfiguration.get_config()
            
            homework_contribution = (self.homework_percentage or Decimal('0.00')) * config.homework_weight / Decimal('100.00')
            classwork_contribution = (self.classwork_percentage or Decimal('0.00')) * config.classwork_weight / Decimal('100.00')
            test_contribution = (self.test_percentage or Decimal('0.00')) * config.test_weight / Decimal('100.00')
            exam_contribution = (self.exam_percentage or Decimal('0.00')) * config.exam_weight / Decimal('100.00')
            
            return {
                'homework': {
                    'percentage': float(self.homework_percentage or 0),
                    'weight': float(config.homework_weight),
                    'contribution': float(homework_contribution)
                },
                'classwork': {
                    'percentage': float(self.classwork_percentage or 0),
                    'weight': float(config.classwork_weight),
                    'contribution': float(classwork_contribution)
                },
                'test': {
                    'percentage': float(self.test_percentage or 0),
                    'weight': float(config.test_weight),
                    'contribution': float(test_contribution)
                },
                'exam': {
                    'percentage': float(self.exam_percentage or 0),
                    'weight': float(config.exam_weight),
                    'contribution': float(exam_contribution)
                }
            }
        except Exception as e:
            logger.error(f"Error getting weighted contributions: {str(e)}")
            return {
                'homework': {'percentage': 0, 'weight': 20, 'contribution': 0},
                'classwork': {'percentage': 0, 'weight': 30, 'contribution': 0},
                'test': {'percentage': 0, 'weight': 10, 'contribution': 0},
                'exam': {'percentage': 0, 'weight': 40, 'contribution': 0}
            }
    
    def get_display_grade(self):
        """Get display grade based on grading system"""
        config = SchoolConfiguration.get_config()
        
        if config.grading_system == 'BOTH':
            return f"{self.ges_grade} ({self.letter_grade})"
        elif config.grading_system == 'GES':
            return self.ges_grade
        else:
            return self.letter_grade
    
    def is_passing(self):
        """Check if grade is passing"""
        try:
            if self.total_score is None:
                return False
                
            config = SchoolConfiguration.get_config()
            return self.total_score >= config.passing_mark
        except:
            return self.total_score >= Decimal('40.00') if self.total_score else False
    
    def get_performance_level(self):
        """Get performance level description"""
        if not self.total_score:
            return 'No Data'
        
        score = float(self.total_score)
        if score >= 80: return 'Excellent'
        elif score >= 70: return 'Very Good'
        elif score >= 60: return 'Good'
        elif score >= 50: return 'Satisfactory'
        elif score >= 40: return 'Fair'
        else: return 'Poor'
    
    def get_performance_level_display(self):
        """Get performance level with color for display"""
        level = self.get_performance_level()
        colors = {
            'Excellent': 'success',
            'Very Good': 'info',
            'Good': 'primary',
            'Satisfactory': 'warning',
            'Fair': 'warning',
            'Poor': 'danger',
            'No Data': 'secondary'
        }
        return {
            'level': level,
            'color': colors.get(level, 'secondary')
        }
    
    def can_be_modified(self):
        """Check if the grade can be modified"""
        return not self.is_locked and not self._is_term_locked()
    
    def _is_term_locked(self):
        """Check if the academic term is locked"""
        try:
            term = AcademicTerm.objects.filter(
                academic_year=self.academic_year.replace('/', '-'),
                term=self.term
            ).first()
            return term.is_locked if term else False
        except:
            return False
    
    def get_or_create_class_assignment(self):
        """Get or create class assignment for this grade"""
        try:
            if not all([self.student, self.subject, self.academic_year]):
                raise ValueError("Missing required fields for class assignment")
            
            target_class_level = self.class_level or getattr(self.student, 'class_level', None)
            if not target_class_level:
                raise ValueError("No class level specified")
            
            formatted_academic_year = self.academic_year.replace('/', '-')
            
            # Look for existing active class assignment
            class_assignment = ClassAssignment.objects.filter(
                class_level=target_class_level,
                subject=self.subject,
                academic_year=formatted_academic_year,
                is_active=True
            ).select_related('teacher', 'teacher__user').first()
            
            if class_assignment:
                return class_assignment
            
            # Create a new class assignment
            teacher = self._find_appropriate_teacher(target_class_level)
            
            if not teacher:
                teacher = self._create_temporary_teacher()
            
            with transaction.atomic():
                class_assignment = ClassAssignment.objects.create(
                    class_level=target_class_level,
                    subject=self.subject,
                    teacher=teacher,
                    academic_year=formatted_academic_year,
                    is_active=True
                )
                
                logger.info(f"Created new class assignment: {class_assignment}")
                return class_assignment
                
        except Exception as e:
            logger.error(f"Failed to get/create class assignment: {str(e)}")
            raise
    
    def _find_appropriate_teacher(self, class_level):
        """Find appropriate teacher for the class assignment"""
        from core.models.teacher import Teacher
        
        try:
            # Find teachers who teach this subject
            subject_teachers = Teacher.objects.filter(
                subjects=self.subject,
                is_active=True
            ).select_related('user')
            
            if subject_teachers.exists():
                # Find teachers who already teach this class level
                for teacher in subject_teachers:
                    if teacher.class_levels:
                        teacher_classes = [cls.strip() for cls in teacher.class_levels.split(',')]
                        if class_level in teacher_classes:
                            return teacher
                
                # Use first available subject teacher
                return subject_teachers.first()
            
            # Find teachers who teach this class level
            class_teachers = Teacher.objects.filter(
                is_active=True
            ).select_related('user')
            
            for teacher in class_teachers:
                if teacher.class_levels:
                    teacher_classes = [cls.strip() for cls in teacher.class_levels.split(',')]
                    if class_level in teacher_classes:
                        return teacher
            
            # Find any active teacher
            return Teacher.objects.filter(is_active=True).first()
            
        except Exception as e:
            logger.error(f"Error finding appropriate teacher: {str(e)}")
            return None
    
    def _create_temporary_teacher(self):
        """Create a temporary teacher record when no teachers are available"""
        from core.models.teacher import Teacher
        
        try:
            # Find or create a system user
            system_user, created = User.objects.get_or_create(
                username='system_teacher',
                defaults={
                    'email': 'system@school.edu',
                    'first_name': 'System',
                    'last_name': 'Teacher',
                    'is_active': True,
                    'is_staff': True
                }
            )
            
            # Generate temporary employee ID
            current_year = str(timezone.now().year)
            teacher_count = Teacher.objects.count()
            employee_id = f"TEMP{current_year}{teacher_count + 1:04d}"
            
            # Create temporary teacher
            teacher = Teacher.objects.create(
                user=system_user,
                employee_id=employee_id,
                date_of_birth=date(1980, 1, 1),
                gender='M',
                phone_number='0240000000',
                address='Temporary System Teacher',
                qualification='System Generated',
                class_levels='P1,P2,P3,P4,P5,P6,J1,J2,J3',
                is_active=True
            )
            
            # Add subject to teacher
            teacher.subjects.add(self.subject)
            
            logger.warning(f"Created temporary teacher {employee_id}")
            return teacher
            
        except Exception as e:
            logger.error(f"Failed to create temporary teacher: {str(e)}")
            return Teacher.objects.filter(is_active=True).first()