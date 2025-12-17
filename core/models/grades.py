"""
Grade and Report Card models.
"""
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

from core.models.base import CLASS_LEVEL_CHOICES, TERM_CHOICES
from core.models.academic import Subject, ClassAssignment, AcademicTerm
from core.models.student import Student

logger = logging.getLogger(__name__)
User = get_user_model()


class Grade(models.Model):
    """
    Enhanced Grade Model with comprehensive validation and business logic.
    """
    
    # Ghana Education Service Standard Weights
    HOMEWORK_WEIGHT = Decimal('10.00')  # 10%
    CLASSWORK_WEIGHT = Decimal('30.00')  # 30%  
    TEST_WEIGHT = Decimal('10.00')       # 10%
    EXAM_WEIGHT = Decimal('50.00')       # 50%

    # GES Grade Choices with detailed descriptions
    GES_GRADE_CHOICES = [
        ('1', '1 (90-100%) - Outstanding - Excellent performance'),
        ('2', '2 (80-89%) - Excellent - Strong performance'), 
        ('3', '3 (70-79%) - Very Good - Above average performance'),
        ('4', '4 (60-69%) - Good - Meets expectations'),
        ('5', '5 (50-59%) - Satisfactory - Needs improvement'),
        ('6', '6 (40-49%) - Fair - Below expectations'),
        ('7', '7 (30-39%) - Weak - Significant improvement needed'),
        ('8', '8 (20-29%) - Very Weak - Concerning performance'),
        ('9', '9 (0-19%) - Fail - Immediate intervention required'),
        ('N/A', 'Not Available'),
    ]

    # Letter Grade Choices
    LETTER_GRADE_CHOICES = [
        ('A+', 'A+ (90-100%) - Outstanding - Excellent performance'),
        ('A', 'A (80-89%) - Excellent - Strong performance'),
        ('B+', 'B+ (70-79%) - Very Good - Above average performance'),
        ('B', 'B (60-69%) - Good - Meets expectations'),
        ('C+', 'C+ (50-59%) - Satisfactory - Needs improvement'),
        ('C', 'C (40-49%) - Fair - Below expectations'),
        ('D+', 'D+ (30-39%) - Weak - Significant improvement needed'),
        ('D', 'D (20-29%) - Very Weak - Concerning performance'),
        ('F', 'F (0-19%) - Fail - Immediate intervention required'),
        ('N/A', 'Not Available'),
    ]

    # Model Fields
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

    # Score fields
    classwork_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(CLASSWORK_WEIGHT, f'Classwork score cannot exceed {CLASSWORK_WEIGHT}%')
        ],
        verbose_name="Classwork Score (30%)",
        default=Decimal('0.00'),
        help_text="Classwork assessment score (0-30%)"
    )
    
    homework_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(HOMEWORK_WEIGHT, f'Homework score cannot exceed {HOMEWORK_WEIGHT}%')
        ],
        verbose_name="Homework Score (10%)",
        default=Decimal('0.00'),
        help_text="Homework assignment score (0-10%)"
    )
    
    test_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(TEST_WEIGHT, f'Test score cannot exceed {TEST_WEIGHT}%')
        ],
        verbose_name="Test Score (10%)", 
        default=Decimal('0.00'),
        help_text="Test/examination score (0-10%)"
    )
    
    exam_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(EXAM_WEIGHT, f'Exam score cannot exceed {EXAM_WEIGHT}%')
        ],
        verbose_name="Exam Score (50%)",
        default=Decimal('0.00'),
        help_text="Final examination score (0-50%)"
    )

    # Calculated fields
    total_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        editable=False, 
        null=True, 
        blank=True,
        verbose_name="Total Score",
        help_text="Automatically calculated total score"
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
    
    # Audit fields
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
            models.Index(fields=['subject', 'academic_year']),
            models.Index(fields=['class_assignment', 'term']),
            models.Index(fields=['total_score']),
            models.Index(fields=['ges_grade']),
            models.Index(fields=['letter_grade']),
            models.Index(fields=['student', 'subject', 'academic_year', 'term']),
            models.Index(fields=['total_score', 'ges_grade']),
            models.Index(fields=['created_at']),
            models.Index(fields=['class_assignment', 'academic_year', 'term']),
            models.Index(fields=['student', 'class_assignment']),
            models.Index(fields=['academic_year', 'term', 'class_level']),
        ]
    
    def __str__(self):
        grade_display = self.get_display_grade()
        return f"{self.student.get_full_name()} - {self.subject.name} ({self.academic_year} Term {self.term}): {grade_display}"
    
    def clean(self):
        """Comprehensive validation for grade data"""
        errors = {}
        
        try:
            # Validate basic field presence
            if not self.student_id:
                errors['student'] = 'Student is required'
            
            if not self.subject_id:
                errors['subject'] = 'Subject is required'
            
            # Validate academic year format and logic
            if self.academic_year:
                if not re.match(r'^\d{4}/\d{4}$', self.academic_year):
                    errors['academic_year'] = 'Academic year must be in format YYYY/YYYY'
                else:
                    # Validate consecutive years
                    try:
                        year1, year2 = map(int, self.academic_year.split('/'))
                        if year2 != year1 + 1:
                            errors['academic_year'] = 'The second year must be exactly one year after the first year'
                    except (ValueError, IndexError):
                        errors['academic_year'] = 'Invalid academic year format'
            
            # Validate term range
            if self.term and self.term not in [1, 2, 3]:
                errors['term'] = 'Term must be 1, 2, or 3'
            
            # Validate score limits with precise decimal validation
            score_fields = {
                'classwork_score': self.CLASSWORK_WEIGHT,
                'homework_score': self.HOMEWORK_WEIGHT,
                'test_score': self.TEST_WEIGHT,
                'exam_score': self.EXAM_WEIGHT,
            }
            
            for field_name, max_score in score_fields.items():
                score = getattr(self, field_name, Decimal('0.00'))
                if score is None:
                    continue
                    
                try:
                    score_decimal = Decimal(str(score))
                    if score_decimal < Decimal('0.00'):
                        errors[field_name] = 'Score cannot be negative'
                    elif score_decimal > max_score:
                        errors[field_name] = f'Score cannot exceed {max_score}%'
                    # Validate decimal precision
                    if abs(score_decimal - score_decimal.quantize(Decimal('0.01'))) > Decimal('0.001'):
                        errors[field_name] = 'Score must have at most 2 decimal places'
                except (InvalidOperation, TypeError, ValueError) as e:
                    errors[field_name] = 'Invalid score format'
                    logger.warning(f"Invalid score format in {field_name}: {score} - {e}")
            
            # Validate total score consistency
            if not errors:
                total_calculated = self._calculate_total_score_safe()
                if total_calculated is not None and total_calculated > Decimal('100.00'):
                    errors['__all__'] = f'Total score cannot exceed 100%. Current calculated total: {total_calculated}%'
            
            # Validate business rules
            self._validate_business_rules(errors)
            
            # Validate against existing grades for uniqueness
            if not errors and self.pk is None:
                self._validate_unique_grade(errors)
            
        except Exception as e:
            logger.error(f"Unexpected error during grade validation: {str(e)}", exc_info=True)
            errors['__all__'] = 'An unexpected validation error occurred. Please try again.'
        
        if errors:
            logger.warning(
                f"Grade validation failed - Student: {getattr(self.student, 'id', 'Unknown')}, "
                f"Subject: {getattr(self.subject, 'name', 'Unknown')}, Errors: {errors}"
            )
            raise ValidationError(errors)
    
    def _validate_business_rules(self, errors):
        """Validate business rules and constraints"""
        try:
            # Check if student is active
            if self.student_id and not self.student.is_active:
                errors['student'] = 'Cannot assign grade to inactive student'
            
            # Check if subject is active
            if self.subject_id and not self.subject.is_active:
                errors['subject'] = 'Cannot assign grade for inactive subject'
            
            # Check if academic term is editable
            if self._is_term_locked():
                errors['__all__'] = 'Cannot modify grades for locked academic term'
            
            # Check if class assignment exists and validate it
            if self.class_assignment_id:
                if self.student_id and self.student.class_level != self.class_assignment.class_level:
                    errors['class_assignment'] = 'Class assignment does not match student class level'
                if self.subject_id and self.subject != self.class_assignment.subject:
                    errors['class_assignment'] = 'Class assignment does not match subject'
            
            # Check for significant changes if updating existing grade
            if self.pk:
                self._validate_grade_changes(errors)
                
        except Exception as e:
            logger.error(f"Business rule validation failed: {str(e)}")
            errors['__all__'] = 'Error validating business rules'
    
    def _validate_unique_grade(self, errors):
        """Validate grade uniqueness constraint"""
        try:
            existing_grade = Grade.objects.filter(
                student=self.student,
                subject=self.subject,
                academic_year=self.academic_year,
                term=self.term
            ).exists()
            
            if existing_grade:
                errors['__all__'] = (
                    'A grade already exists for this student, subject, term, and academic year. '
                    'Please update the existing grade instead.'
                )
        except Exception as e:
            logger.error(f"Unique grade validation failed: {str(e)}")
            errors['__all__'] = 'Error checking for duplicate grades'
    
    def _validate_grade_changes(self, errors):
        """Validate changes to existing grade for significant modifications"""
        try:
            original_grade = Grade.objects.get(pk=self.pk)
            
            # Check if grade is locked
            if original_grade.is_locked:
                errors['__all__'] = 'This grade is locked and cannot be modified'
                return
            
            # Check for significant score changes
            significant_changes = []
            score_fields = ['classwork_score', 'homework_score', 'test_score', 'exam_score']
            
            for field in score_fields:
                original_value = getattr(original_grade, field, Decimal('0.00'))
                new_value = getattr(self, field, Decimal('0.00'))
                
                if abs(float(new_value) - float(original_value)) > 20.0:
                    significant_changes.append(field.replace('_score', ''))
            
            if significant_changes:
                self.requires_review = True
                logger.info(
                    f"Grade marked for review due to significant changes - "
                    f"Grade ID: {self.pk}, Changes: {significant_changes}"
                )
                
        except Grade.DoesNotExist:
            logger.warning(f"Original grade not found during change validation - PK: {self.pk}")
        except Exception as e:
            logger.error(f"Grade change validation failed: {str(e)}")
    
    def _is_term_locked(self):
        """Check if the academic term is locked for editing"""
        try:
            term_obj = AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                term=self.term
            ).first()
            
            if term_obj and getattr(term_obj, 'is_locked', False):
                return True
                
            return False
        except Exception as e:
            logger.warning(f"Error checking term lock status: {str(e)}")
            return False
    
    def _calculate_total_score_safe(self):
        """Safely calculate total score without side effects"""
        try:
            scores = [
                self.classwork_score or Decimal('0.00'),
                self.homework_score or Decimal('0.00'),
                self.test_score or Decimal('0.00'),
                self.exam_score or Decimal('0.00')
            ]
            
            total = sum(score for score in scores if score is not None)
            return total.quantize(Decimal('0.01'))
            
        except (TypeError, InvalidOperation, ValueError) as e:
            logger.error(f"Error in safe total score calculation: {str(e)}")
            return None
    
    @transaction.atomic
    def save(self, *args, **kwargs):
        """Enhanced save method with comprehensive error handling"""
        try:
            # Pre-save validation
            is_new = self.pk is None
            
            # Set class_level from student if not set
            if self.student and not self.class_level:
                self.class_level = self.student.class_level
            
            # Auto-create class_assignment if not set
            if not self.class_assignment_id and self.student and self.subject and self.academic_year:
                try:
                    self.class_assignment = self.get_or_create_class_assignment()
                except Exception as e:
                    logger.warning(f"Could not auto-create class assignment: {e}")
            
            # Run full validation
            self.full_clean()
            
            # Pre-save calculations
            self._pre_save_calculations()
            
            # Save the instance
            super().save(*args, **kwargs)
            
            logger.info(
                f"Grade saved successfully - ID: {self.pk}, "
                f"Student: {self.student_id}, Subject: {self.subject_id}, "
                f"Total Score: {self.total_score}, GES Grade: {self.ges_grade}, Letter Grade: {self.letter_grade}"
            )
            
        except ValidationError as e:
            logger.error(
                f"Grade validation failed during save - "
                f"Student: {getattr(self.student, 'id', 'Unknown')}, "
                f"Subject: {getattr(self.subject, 'name', 'Unknown')}, "
                f"Errors: {e.message_dict}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error saving grade - "
                f"Student: {getattr(self.student, 'id', 'Unknown')}, "
                f"Subject: {getattr(self.subject, 'name', 'Unknown')}, "
                f"Error: {str(e)}",
                exc_info=True
            )
            raise
    
    def _pre_save_calculations(self):
        """Perform all calculations before saving"""
        try:
            # Calculate total score
            self.calculate_total_score()
            
            # Determine both GES and Letter grades
            self.determine_grades()
            
            # Update timestamps
            if not self.pk:
                self.created_at = timezone.now()
            
        except Exception as e:
            logger.error(f"Pre-save calculations failed: {str(e)}")
            raise
    
    def calculate_total_score(self):
        """Calculate total score with comprehensive error handling"""
        try:
            scores = [
                self.classwork_score,
                self.homework_score, 
                self.test_score,
                self.exam_score
            ]
            
            # Convert to Decimal and handle None values
            decimal_scores = []
            for score in scores:
                if score is None:
                    decimal_scores.append(Decimal('0.00'))
                else:
                    try:
                        decimal_scores.append(Decimal(str(score)))
                    except (InvalidOperation, TypeError, ValueError):
                        decimal_scores.append(Decimal('0.00'))
                        logger.warning(f"Invalid score converted to 0: {score}")
            
            total = sum(decimal_scores)
            self.total_score = total.quantize(Decimal('0.01'))
            
            logger.debug(f"Total score calculated: {self.total_score} for grade {self.pk}")
            
        except Exception as e:
            logger.error(f"Error calculating total score: {str(e)}", exc_info=True)
            self.total_score = None
            raise
    
    def determine_grades(self):
        """Determine both GES and letter grades based on Ghana Education Service standards"""
        try:
            if self.total_score is None:
                self.ges_grade = 'N/A'
                self.letter_grade = 'N/A'
                return

            score = float(self.total_score)
            
            # GES grading standards
            if score >= 90: 
                self.ges_grade = '1'
            elif score >= 80: 
                self.ges_grade = '2'
            elif score >= 70: 
                self.ges_grade = '3'
            elif score >= 60: 
                self.ges_grade = '4' 
            elif score >= 50: 
                self.ges_grade = '5'
            elif score >= 40: 
                self.ges_grade = '6'
            elif score >= 30: 
                self.ges_grade = '7'
            elif score >= 20: 
                self.ges_grade = '8'
            else: 
                self.ges_grade = '9'
            
            # Letter grading standards
            if score >= 90: 
                self.letter_grade = 'A+'
            elif score >= 80: 
                self.letter_grade = 'A'
            elif score >= 70: 
                self.letter_grade = 'B+'
            elif score >= 60: 
                self.letter_grade = 'B'
            elif score >= 50: 
                self.letter_grade = 'C+'
            elif score >= 40: 
                self.letter_grade = 'C'
            elif score >= 30: 
                self.letter_grade = 'D+'
            elif score >= 20: 
                self.letter_grade = 'D'
            else: 
                self.letter_grade = 'F'
                
            logger.debug(f"Grades determined - GES: {self.ges_grade}, Letter: {self.letter_grade} for score {score}")
            
        except (TypeError, ValueError) as e:
            logger.error(f"Error determining grades: {str(e)}")
            self.ges_grade = 'N/A'
            self.letter_grade = 'N/A'
        except Exception as e:
            logger.error(f"Unexpected error determining grades: {str(e)}", exc_info=True)
            self.ges_grade = 'N/A'
            self.letter_grade = 'N/A'
    
    def get_display_grade(self):
        """Get the grade to display based on system configuration"""
        try:
            # Try to import from grading_utils if it exists
            from core.grading_utils import get_display_grade as get_system_display_grade
            return get_system_display_grade(self.ges_grade, self.letter_grade)
        except ImportError:
            # Fallback if grading_utils doesn't exist
            if self.ges_grade and self.ges_grade != 'N/A' and self.letter_grade and self.letter_grade != 'N/A':
                return f"{self.ges_grade} ({self.letter_grade})"
            elif self.ges_grade and self.ges_grade != 'N/A':
                return self.ges_grade
            elif self.letter_grade and self.letter_grade != 'N/A':
                return self.letter_grade
            else:
                return 'N/A'
        except Exception as e:
            logger.error(f"Error getting display grade: {str(e)}")
            # Fallback to showing both if there's an error
            if self.ges_grade and self.ges_grade != 'N/A' and self.letter_grade and self.letter_grade != 'N/A':
                return f"{self.ges_grade} ({self.letter_grade})"
            elif self.ges_grade and self.ges_grade != 'N/A':
                return self.ges_grade
            elif self.letter_grade and self.letter_grade != 'N/A':
                return self.letter_grade
            else:
                return 'N/A'
    
    def is_passing(self):
        """Check if grade is passing (GES standards - 40% and above)"""
        try:
            return self.total_score and Decimal(str(self.total_score)) >= Decimal('40.00')
        except (TypeError, ValueError, InvalidOperation):
            return False
    
    def get_performance_level_display(self):
        """Get performance level display name"""
        if not self.total_score:
            return 'Not Available'
        if self.total_score >= 80: return 'Excellent'
        elif self.total_score >= 70: return 'Very Good'
        elif self.total_score >= 60: return 'Good'
        elif self.total_score >= 50: return 'Satisfactory'
        elif self.total_score >= 40: return 'Fair'
        else: return 'Poor'
    
    def score_breakdown(self):
        """Get score breakdown for templates"""
        return {
            'classwork': self.classwork_score or 0,
            'homework': self.homework_score or 0,
            'test': self.test_score or 0,
            'exam': self.exam_score or 0,
        }
    
    @property
    def can_be_modified(self):
        """Check if the grade can be modified"""
        return not self.is_locked and not self._is_term_locked()
    
    def get_or_create_class_assignment(self):
        """Get or create class assignment for this grade"""
        from core.models.academic import ClassAssignment
        from core.models.teacher import Teacher
        
        try:
            if not all([self.student, self.subject, self.academic_year]):
                raise ValueError(
                    "Missing required fields for class assignment: "
                    "student, subject, and academic year are required"
                )
            
            target_class_level = self.class_level or getattr(self.student, 'class_level', None)
            if not target_class_level:
                raise ValueError("No class level specified for class assignment")
            
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
            
            # No existing assignment found - create a new one
            teacher = self._find_appropriate_teacher(target_class_level)
            
            if not teacher:
                # Create a temporary teacher if none found
                teacher = self._create_temporary_teacher()
            
            # Create the class assignment
            with transaction.atomic():
                class_assignment = ClassAssignment.objects.create(
                    class_level=target_class_level,
                    subject=self.subject,
                    teacher=teacher,
                    academic_year=formatted_academic_year,
                    is_active=True
                )
                
                logger.info(
                    f"Created new class assignment - ID: {class_assignment.id}, "
                    f"Class: {target_class_level}, Subject: {self.subject.name}, "
                    f"Teacher: {teacher.employee_id}, Year: {formatted_academic_year}"
                )
                
                return class_assignment
                
        except Exception as e:
            logger.error(
                f"Failed to get/create class assignment - "
                f"Student: {getattr(self.student, 'id', 'Unknown')}, "
                f"Subject: {getattr(self.subject, 'name', 'Unknown')}, "
                f"Error: {str(e)}",
                exc_info=True
            )
            raise
    
    def _find_appropriate_teacher(self, class_level):
        """Find appropriate teacher for the class assignment"""
        from core.models.teacher import Teacher
        
        try:
            # Strategy 1: Find teachers who teach this subject
            subject_teachers = Teacher.objects.filter(
                subjects=self.subject,
                is_active=True
            ).select_related('user')
            
            if subject_teachers.exists():
                # Strategy 1a: Find teachers who already teach this class level
                for teacher in subject_teachers:
                    if teacher.class_levels:
                        teacher_classes = [cls.strip() for cls in teacher.class_levels.split(',')]
                        if class_level in teacher_classes:
                            logger.debug(f"Found teacher {teacher.employee_id} for class {class_level}")
                            return teacher
                
                # Strategy 1b: Use first available subject teacher
                teacher = subject_teachers.first()
                logger.debug(f"Using subject teacher {teacher.employee_id} for class {class_level}")
                return teacher
            
            # Strategy 2: Find teachers who teach this class level
            class_teachers = Teacher.objects.filter(
                is_active=True
            ).select_related('user')
            
            for teacher in class_teachers:
                if teacher.class_levels:
                    teacher_classes = [cls.strip() for cls in teacher.class_levels.split(',')]
                    if class_level in teacher_classes:
                        logger.debug(f"Found class teacher {teacher.employee_id} for class {class_level}")
                        return teacher
            
            # Strategy 3: Find any active teacher
            any_teacher = Teacher.objects.filter(is_active=True).first()
            if any_teacher:
                logger.debug(f"Using available teacher {any_teacher.employee_id} for class {class_level}")
                return any_teacher
            
            logger.warning(f"No active teachers found for class {class_level}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding appropriate teacher: {str(e)}", exc_info=True)
            return None
    
    def _create_temporary_teacher(self):
        """Create a temporary teacher record when no teachers are available"""
        from core.models.teacher import Teacher
        
        try:
            # Find or create a system user for temporary teachers
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
            
            logger.warning(f"Created temporary teacher {employee_id} for subject {self.subject.name}")
            
            return teacher
            
        except Exception as e:
            logger.error(f"Failed to create temporary teacher: {str(e)}", exc_info=True)
            return Teacher.objects.filter(is_active=True).first()


class ReportCard(models.Model):
    TERM_CHOICES = TERM_CHOICES
    
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
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(3)])
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    overall_grade = models.CharField(max_length=2, choices=GRADE_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    teacher_remarks = models.TextField(blank=True)
    principal_remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = ('student', 'academic_year', 'term')
        ordering = ['-academic_year', '-term']
        verbose_name = 'Report Card'
        verbose_name_plural = 'Report Cards'
    
    def __str__(self):
        return f"{self.student}'s Report Card - {self.academic_year} Term {self.term}"
    
    def save(self, *args, **kwargs):
        if not self.average_score or not self.overall_grade:
            self.calculate_grades()
        super().save(*args, **kwargs)
    
    def calculate_grades(self):
        """Calculate average score and overall grade from student's grades"""
        grades = Grade.objects.filter(
            student=self.student,
            academic_year=self.academic_year,
            term=self.term
        )
        
        if grades.exists():
            total_score = sum(grade.total_score for grade in grades if grade.total_score)
            self.average_score = total_score / grades.count()
            self.overall_grade = self.calculate_grade(self.average_score)
        else:
            self.average_score = 0.00
            self.overall_grade = ''
    
    @staticmethod
    def calculate_grade(score):
        """Calculate letter grade based on score"""
        if not score:
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