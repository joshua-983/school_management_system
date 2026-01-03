# models/configuration.py - CORRECTED VERSION
"""
System configuration models.
"""
import logging
import re
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# UPDATE IMPORTS TO INCLUDE ACADEMIC_PERIOD_SYSTEM_CHOICES
from core.models.base import (
    TERM_CHOICES, 
    CLASS_LEVEL_CHOICES,
    ACADEMIC_PERIOD_SYSTEM_CHOICES  # ADDED
)

logger = logging.getLogger(__name__)
User = get_user_model()


class SchoolConfiguration(models.Model):
    """Main school configuration model with comprehensive grading system settings."""
    
    # Grading System Choices
    GRADING_SYSTEM_CHOICES = [
        ('GES', 'Ghana Education System (1-9)'),
        ('LETTER', 'Letter Grading System (A-F)'),
        ('BOTH', 'Both Systems'),
        ('CUSTOM', 'Custom Grading System'),
    ]
    
    # School Level Choices
    SCHOOL_LEVEL_CHOICES = [
        ('PRIMARY', 'Primary School (P1-P6)'),
        ('JHS', 'Junior High School (JHS1-JHS3)'),
        ('COMBINED', 'Combined Primary and JHS'),
        ('SHS', 'Senior High School'),
        ('OTHER', 'Other'),
    ]
    
    # Grading System Configuration
    grading_system = models.CharField(
        max_length=10, 
        choices=GRADING_SYSTEM_CHOICES, 
        default='GES',
        verbose_name="Grading System",
        help_text="Select the grading system to use"
    )
    
    # School Level Information
    school_level = models.CharField(
        max_length=20, 
        choices=SCHOOL_LEVEL_CHOICES, 
        default='COMBINED',
        verbose_name="School Level",
        help_text="Select the school level"
    )
    
    # Grade Boundary Configuration (GES 1-9 System)
    grade_1_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=90.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Grade 1 Minimum",
        help_text="Minimum percentage for Grade 1 (Excellent)"
    )
    
    grade_2_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=80.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Grade 2 Minimum",
        help_text="Minimum percentage for Grade 2 (Very Good)"
    )
    
    grade_3_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=70.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Grade 3 Minimum",
        help_text="Minimum percentage for Grade 3 (Good)"
    )
    
    grade_4_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=60.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Grade 4 Minimum",
        help_text="Minimum percentage for Grade 4 (Credit)"
    )
    
    grade_5_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=50.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Grade 5 Minimum",
        help_text="Minimum percentage for Grade 5 (Credit)"
    )
    
    grade_6_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=40.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Grade 6 Minimum",
        help_text="Minimum percentage for Grade 6 (Pass)"
    )
    
    grade_7_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=30.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Grade 7 Minimum",
        help_text="Minimum percentage for Grade 7 (Pass)"
    )
    
    grade_8_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=20.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Grade 8 Minimum",
        help_text="Minimum percentage for Grade 8 (Weak)"
    )
    
    grade_9_max = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=19.99,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Grade 9 Maximum",
        help_text="Maximum percentage for Grade 9 (Very Weak/Fail)"
    )
    
    # Letter Grade Boundary Configuration
    letter_a_plus_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=90.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="A+ Minimum",
        help_text="Minimum percentage for A+"
    )
    
    letter_a_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=80.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="A Minimum",
        help_text="Minimum percentage for A"
    )
    
    letter_b_plus_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=70.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="B+ Minimum",
        help_text="Minimum percentage for B+"
    )
    
    letter_b_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=60.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="B Minimum",
        help_text="Minimum percentage for B"
    )
    
    letter_c_plus_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=50.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="C+ Minimum",
        help_text="Minimum percentage for C+"
    )
    
    letter_c_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=40.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="C Minimum",
        help_text="Minimum percentage for C"
    )
    
    letter_d_plus_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=30.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="D+ Minimum",
        help_text="Minimum percentage for D+"
    )
    
    letter_d_min = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=20.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="D Minimum",
        help_text="Minimum percentage for D"
    )
    
    letter_f_max = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=19.99,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="F Maximum",
        help_text="Maximum percentage for F (Fail)"
    )
    
    # Assessment Weight Configuration
    classwork_weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=30.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Classwork Weight (%)",
        help_text="Percentage weight for classwork assessments"
    )
    
    homework_weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Homework Weight (%)",
        help_text="Percentage weight for homework assignments"
    )
    
    test_weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Test Weight (%)",
        help_text="Percentage weight for tests"
    )
    
    exam_weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=50.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Exam Weight (%)",
        help_text="Percentage weight for final examinations"
    )
    
    # Pass/Fail Configuration
    passing_mark = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=40.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Passing Mark (%)",
        help_text="Minimum percentage required to pass"
    )
    
    # Grade Locking
    is_locked = models.BooleanField(
        default=False, 
        verbose_name="Configuration Locked",
        help_text="Lock the configuration to prevent changes"
    )
    
    # Academic Information
    academic_year = models.CharField(
        max_length=9, 
        default=f"{timezone.now().year}/{timezone.now().year + 1}",
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Academic year must be in format YYYY/YYYY')],
        verbose_name="Current Academic Year"
    )
    
    current_term = models.PositiveSmallIntegerField(
        choices=TERM_CHOICES, 
        default=1,
        verbose_name="Current Term"
    )
    
    has_three_terms = models.BooleanField(
        default=True, 
        verbose_name="Three-Term System",
        help_text="School operates on 3-term system"
    )
    
    # NEW: Academic Period System
    academic_period_system = models.CharField(
        max_length=10,
        choices=ACADEMIC_PERIOD_SYSTEM_CHOICES,
        default='TERM',
        verbose_name="Academic Period System",
        help_text="System used for academic periods (Terms, Semesters, etc.)"
    )
    
    # School Information
    school_name = models.CharField(
        max_length=200, 
        default="Ghana Education Service School",
        verbose_name="School Name"
    )
    
    school_address = models.TextField(
        default="",
        verbose_name="School Address"
    )
    
    school_phone = models.CharField(
        max_length=10,
        blank=True,
        validators=[
            RegexValidator(
                r'^0\d{9}$',
                message="Phone number must be 10 digits starting with 0 (e.g., 0245478847)"
            )
        ],
        verbose_name="School Phone",
        help_text="10-digit phone number starting with 0 (e.g., 0245478847)"
    )
    
    school_email = models.EmailField(
        blank=True,
        verbose_name="School Email"
    )
    
    principal_name = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name="Principal's Name"
    )
    
    # Timestamps
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Last Updated")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    
    class Meta:
        verbose_name = "School Configuration"
        verbose_name_plural = "School Configuration"
    
    def save(self, *args, **kwargs):
        """Override save to ensure only one configuration exists."""
        if SchoolConfiguration.objects.exists() and not self.pk:
            raise ValidationError("Only one school configuration can exist")
        
        # Clean phone number before saving
        if self.school_phone:
            self.school_phone = self.school_phone.replace(' ', '').replace('-', '')
        
        # Validate weight totals
        self._validate_weights()
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Additional validation for configuration."""
        errors = {}
        
        # Phone number validation
        if self.school_phone:
            cleaned_phone = self.school_phone.replace(' ', '').replace('-', '')
            if len(cleaned_phone) != 10 or not cleaned_phone.startswith('0'):
                errors['school_phone'] = 'Phone number must be exactly 10 digits starting with 0'
            self.school_phone = cleaned_phone
        
        # Validate academic year format
        if self.academic_year:
            if not re.match(r'^\d{4}/\d{4}$', self.academic_year):
                errors['academic_year'] = 'Academic year must be in format YYYY/YYYY'
            else:
                try:
                    year1, year2 = map(int, self.academic_year.split('/'))
                    if year2 != year1 + 1:
                        errors['academic_year'] = 'The second year must be exactly one year after the first year'
                except (ValueError, IndexError):
                    errors['academic_year'] = 'Invalid academic year format'
        
        # Validate grade boundaries are in descending order
        grade_boundaries = [
            self.grade_1_min, self.grade_2_min, self.grade_3_min, self.grade_4_min,
            self.grade_5_min, self.grade_6_min, self.grade_7_min, self.grade_8_min
        ]
        
        for i in range(len(grade_boundaries) - 1):
            if grade_boundaries[i] <= grade_boundaries[i + 1]:
                errors[f'grade_{i+1}_min'] = f'Grade {i+1} minimum must be greater than Grade {i+2} minimum'
        
        # Validate letter grade boundaries
        letter_boundaries = [
            self.letter_a_plus_min, self.letter_a_min, self.letter_b_plus_min,
            self.letter_b_min, self.letter_c_plus_min, self.letter_c_min,
            self.letter_d_plus_min, self.letter_d_min
        ]
        
        for i in range(len(letter_boundaries) - 1):
            if letter_boundaries[i] <= letter_boundaries[i + 1]:
                boundary_names = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D']
                errors[f'letter_{boundary_names[i].lower().replace("+", "_plus")}_min'] = \
                    f'{boundary_names[i]} minimum must be greater than {boundary_names[i+1]} minimum'
        
        # Validate passing mark is reasonable
        if self.passing_mark and self.passing_mark > self.grade_6_min:
            errors['passing_mark'] = f'Passing mark cannot be higher than Grade 6 minimum ({self.grade_6_min}%)'
        
        if errors:
            raise ValidationError(errors)
    
    def _validate_weights(self):
        """Validate that assessment weights total 100%."""
        total_weight = (
            float(self.classwork_weight) +
            float(self.homework_weight) +
            float(self.test_weight) +
            float(self.exam_weight)
        )
        
        if abs(total_weight - 100.00) > 0.01:  # Allow small floating point differences
            raise ValidationError(
                f"Assessment weights must total 100%. Current total: {total_weight:.2f}%"
            )
    
    def __str__(self):
        return f"School Configuration - {self.school_name}"
    
    @classmethod
    def get_config(cls):
        """Get or create the single configuration instance."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def get_grading_system_display_name(self):
        """Get user-friendly grading system name."""
        return dict(self.GRADING_SYSTEM_CHOICES).get(self.grading_system, 'GES')
    
    def get_school_level_display_name(self):
        """Get user-friendly school level name."""
        return dict(self.SCHOOL_LEVEL_CHOICES).get(self.school_level, 'COMBINED')
    
    def get_current_academic_period(self):
        """Get the current academic period based on configuration"""
        from core.models.academic import AcademicTerm
        
        current_period = AcademicTerm.objects.filter(
            academic_year=self.academic_year,
            period_system=self.academic_period_system,
            is_active=True
        ).first()
        
        return current_period
    
    def get_ges_grade_for_score(self, score):
        """Get GES grade (1-9) for a given score."""
        if score is None:
            return 'N/A'
        
        try:
            score = float(score)
            if score >= float(self.grade_1_min):
                return '1'
            elif score >= float(self.grade_2_min):
                return '2'
            elif score >= float(self.grade_3_min):
                return '3'
            elif score >= float(self.grade_4_min):
                return '4'
            elif score >= float(self.grade_5_min):
                return '5'
            elif score >= float(self.grade_6_min):
                return '6'
            elif score >= float(self.grade_7_min):
                return '7'
            elif score >= float(self.grade_8_min):
                return '8'
            else:
                return '9'
        except (ValueError, TypeError):
            return 'N/A'
    
    def get_letter_grade_for_score(self, score):
        """Get letter grade for a given score."""
        if score is None:
            return 'N/A'
        
        try:
            score = float(score)
            if score >= float(self.letter_a_plus_min):
                return 'A+'
            elif score >= float(self.letter_a_min):
                return 'A'
            elif score >= float(self.letter_b_plus_min):
                return 'B+'
            elif score >= float(self.letter_b_min):
                return 'B'
            elif score >= float(self.letter_c_plus_min):
                return 'C+'
            elif score >= float(self.letter_c_min):
                return 'C'
            elif score >= float(self.letter_d_plus_min):
                return 'D+'
            elif score >= float(self.letter_d_min):
                return 'D'
            else:
                return 'F'
        except (ValueError, TypeError):
            return 'N/A'
    
    def get_all_grades_for_score(self, score):
        """Get both GES and letter grades for a score."""
        return {
            'ges_grade': self.get_ges_grade_for_score(score),
            'letter_grade': self.get_letter_grade_for_score(score),
            'score': score,
            'is_passing': score >= float(self.passing_mark) if score is not None else False
        }
    
    def is_score_passing(self, score):
        """Check if a score is passing."""
        if score is None:
            return False
        return float(score) >= float(self.passing_mark)
    
    def get_grade_description(self, ges_grade, letter_grade):
        """Get grade description based on active system."""
        descriptions = self.get_grade_descriptions()
        
        if self.grading_system == 'GES':
            return descriptions['GES'].get(ges_grade, 'Not graded')
        elif self.grading_system == 'LETTER':
            return descriptions['LETTER'].get(letter_grade, 'Not graded')
        else:
            ges_desc = descriptions['GES'].get(ges_grade, 'Not graded')
            letter_desc = descriptions['LETTER'].get(letter_grade, 'Not graded')
            return f"GES: {ges_desc} | Letter: {letter_desc}"
    
    def get_grade_descriptions(self):
        """Get descriptions for both grading systems."""
        return {
            'GES': {
                '1': 'Excellent - Outstanding performance',
                '2': 'Very Good - Strong performance',
                '3': 'Good - Above average performance',
                '4': 'Satisfactory - Meets expectations',
                '5': 'Fair - Needs improvement',
                '6': 'Marginal - Below expectations',
                '7': 'Poor - Significant improvement needed',
                '8': 'Very Poor - Concerning performance',
                '9': 'Fail - Immediate intervention required',
                'N/A': 'Grade not available'
            },
            'LETTER': {
                'A+': 'Excellent - Outstanding performance',
                'A': 'Excellent - Strong performance',
                'B+': 'Very Good - Above average',
                'B': 'Good - Meets expectations',
                'C+': 'Satisfactory - Average performance',
                'C': 'Fair - Needs improvement',
                'D+': 'Marginal - Below expectations',
                'D': 'Poor - Significant improvement needed',
                'F': 'Fail - Immediate intervention required',
                'N/A': 'Grade not available'
            }
        }
    
    def get_grade_color(self, ges_grade):
        """Get color for grade display."""
        if not ges_grade or ges_grade == 'N/A':
            return 'secondary'
        
        colors = {
            '1': 'success',    # Green
            '2': 'success',    # Green
            '3': 'info',       # Blue
            '4': 'info',       # Blue
            '5': 'warning',    # Yellow
            '6': 'warning',    # Yellow
            '7': 'danger',     # Red
            '8': 'danger',     # Red
            '9': 'danger',     # Red
        }
        return colors.get(ges_grade, 'secondary')
    
    def get_assessment_weights(self):
        """Get assessment weights as a dictionary."""
        return {
            'classwork': float(self.classwork_weight),
            'homework': float(self.homework_weight),
            'test': float(self.test_weight),
            'exam': float(self.exam_weight),
        }
    
    def apply_defaults_for_school_level(self):
        """Apply default settings based on school level."""
        if self.school_level == 'PRIMARY':
            # Primary school defaults
            self.grade_6_min = Decimal('40.00')
            self.grade_7_min = Decimal('30.00')
            self.passing_mark = Decimal('40.00')
            self.classwork_weight = Decimal('40.00')
            self.exam_weight = Decimal('60.00')
            self.homework_weight = Decimal('0.00')
            self.test_weight = Decimal('0.00')
        
        elif self.school_level == 'JHS':
            # JHS defaults (official GES)
            self.grade_6_min = Decimal('45.00')  # Official GES: 45% for Grade 6
            self.grade_7_min = Decimal('35.00')  # Official GES: 35% for Grade 7
            self.passing_mark = Decimal('45.00')
            self.classwork_weight = Decimal('30.00')
            self.homework_weight = Decimal('10.00')
            self.test_weight = Decimal('10.00')
            self.exam_weight = Decimal('50.00')
        
        elif self.school_level == 'SHS':
            # SHS defaults
            self.grade_6_min = Decimal('45.00')
            self.grade_7_min = Decimal('35.00')
            self.passing_mark = Decimal('45.00')
            self.classwork_weight = Decimal('40.00')
            self.homework_weight = Decimal('10.00')
            self.test_weight = Decimal('10.00')
            self.exam_weight = Decimal('40.00')
        
        # Ensure weights total 100%
        self._validate_weights()
    
    def get_display_grade_for_score(self, score):
        """Get display grade based on score and grading system"""
        try:
            score = float(score)
            if self.grading_system == 'GES':
                return self.get_ges_grade_for_score(score)
            elif self.grading_system == 'LETTER':
                return self.get_letter_grade_for_score(score)
            elif self.grading_system == 'BOTH':
                ges_grade = self.get_ges_grade_for_score(score)
                letter_grade = self.get_letter_grade_for_score(score)
                return f"{ges_grade} ({letter_grade})"
            else:  # CUSTOM or any other
                ges_grade = self.get_ges_grade_for_score(score)
                letter_grade = self.get_letter_grade_for_score(score)
                return f"{ges_grade} / {letter_grade}"
        except (ValueError, TypeError):
            return "N/A"

    def get_grade_color_for_display(self, grade):
        """Get Bootstrap color class for grade display"""
        if grade in ['1', '2', 'A+', 'A']:
            return 'success'
        elif grade in ['3', '4', 'B+', 'B']:
            return 'info'
        elif grade in ['5', '6', 'C+', 'C']:
            return 'warning'
        elif grade in ['7', '8', 'D+', 'D']:
            return 'warning'
        elif grade in ['9', 'F', 'E']:
            return 'danger'
        else:
            return 'secondary'

    def create_academic_periods_for_year(self):
        """Create academic periods for the current academic year"""
        from core.models.academic import AcademicTerm
        
        try:
            # Check if periods already exist
            existing = AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                period_system=self.academic_period_system
            ).exists()
            
            if existing:
                return False, f"Academic periods for {self.academic_year} already exist."
            
            # Create periods
            periods = AcademicTerm.create_academic_year(
                academic_year=self.academic_year,
                period_system=self.academic_period_system
            )
            
            return True, f"Created {len(periods)} academic periods for {self.academic_year} ({self.academic_period_system})"
            
        except Exception as e:
            return False, f"Error creating academic periods: {str(e)}"
    
    def get_period_system_display(self):
        """Get display name for academic period system"""
        system_map = dict(ACADEMIC_PERIOD_SYSTEM_CHOICES)
        return system_map.get(self.academic_period_system, 'Term System')


class ReportCardConfiguration(models.Model):
    """Configuration for report card generation and display."""
    
    school_config = models.OneToOneField(
        SchoolConfiguration, 
        on_delete=models.CASCADE,
        related_name='report_card_config'
    )
    
    # Content Configuration
    include_comments = models.BooleanField(
        default=True,
        verbose_name="Include Teacher Comments",
        help_text="Include teacher comments on report cards"
    )
    
    include_attendance = models.BooleanField(
        default=True,
        verbose_name="Include Attendance",
        help_text="Include attendance records on report cards"
    )
    
    include_conduct = models.BooleanField(
        default=True,
        verbose_name="Include Conduct",
        help_text="Include conduct/behavior assessment on report cards"
    )
    
    include_extracurricular = models.BooleanField(
        default=False,
        verbose_name="Include Extracurricular",
        help_text="Include extracurricular activities on report cards"
    )
    
    # Signature Requirements
    principal_signature_required = models.BooleanField(
        default=True,
        verbose_name="Principal Signature Required",
        help_text="Require principal's signature on report cards"
    )
    
    class_teacher_signature_required = models.BooleanField(
        default=True,
        verbose_name="Class Teacher Signature Required",
        help_text="Require class teacher's signature on report cards"
    )
    
    # Additional Information
    include_next_term_begins_date = models.BooleanField(
        default=True,
        verbose_name="Include Next Term Date",
        help_text="Include next term begins date on report cards"
    )
    
    include_house_master_comment = models.BooleanField(
        default=False,
        verbose_name="Include House Master Comment",
        help_text="Include house master's comment (for boarding schools)"
    )
    
    include_counselor_comment = models.BooleanField(
        default=False,
        verbose_name="Include Counselor Comment",
        help_text="Include guidance counselor's comment"
    )
    
    # Layout and Display Options
    show_grade_descriptions = models.BooleanField(
        default=True,
        verbose_name="Show Grade Descriptions",
        help_text="Show grade descriptions on report cards"
    )
    
    show_score_breakdown = models.BooleanField(
        default=True,
        verbose_name="Show Score Breakdown",
        help_text="Show breakdown of scores (classwork, homework, test, exam)"
    )
    
    show_class_position = models.BooleanField(
        default=True,
        verbose_name="Show Class Position",
        help_text="Show student's position in class"
    )
    
    show_overall_position = models.BooleanField(
        default=True,
        verbose_name="Show Overall Position",
        help_text="Show student's overall position in school"
    )
    
    show_grade_color_coding = models.BooleanField(
        default=True,
        verbose_name="Use Color Coding",
        help_text="Use color coding for grades on report cards"
    )
    
    # Report Card Design
    school_logo = models.ImageField(
        upload_to='school_logos/',
        blank=True,
        null=True,
        verbose_name="School Logo",
        help_text="Logo to display on report cards"
    )
    
    header_color = models.CharField(
        max_length=7,
        default='#2E7D32',  # Green
        verbose_name="Header Color",
        help_text="Color for report card header (hex code)"
    )
    
    footer_text = models.TextField(
        blank=True,
        verbose_name="Footer Text",
        help_text="Text to display in report card footer"
    )
    
    # Print Settings
    paper_size = models.CharField(
        max_length=20,
        choices=[
            ('A4', 'A4'),
            ('LETTER', 'Letter'),
            ('LEGAL', 'Legal'),
        ],
        default='A4',
        verbose_name="Paper Size"
    )
    
    orientation = models.CharField(
        max_length=10,
        choices=[
            ('PORTRAIT', 'Portrait'),
            ('LANDSCAPE', 'Landscape'),
        ],
        default='PORTRAIT',
        verbose_name="Orientation"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    
    class Meta:
        verbose_name = "Report Card Configuration"
        verbose_name_plural = "Report Card Configuration"
    
    def __str__(self):
        return f"Report Card Configuration - {self.school_config.school_name}"
    
    @classmethod
    def get_or_create_for_school(cls):
        """Get or create report card configuration for the school."""
        school_config = SchoolConfiguration.get_config()
        obj, created = cls.objects.get_or_create(school_config=school_config)
        return obj


class PromotionConfiguration(models.Model):
    """Configuration for student promotion rules."""
    
    school_config = models.OneToOneField(
        SchoolConfiguration, 
        on_delete=models.CASCADE,
        related_name='promotion_config'
    )
    
    # Primary School Promotion Rules
    primary_pass_mark = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=40.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Primary Pass Mark (%)",
        help_text="Minimum percentage to pass in primary school"
    )
    
    primary_must_pass_english = models.BooleanField(
        default=True,
        verbose_name="Must Pass English (Primary)",
        help_text="Students must pass English to be promoted"
    )
    
    primary_must_pass_maths = models.BooleanField(
        default=True,
        verbose_name="Must Pass Mathematics (Primary)",
        help_text="Students must pass Mathematics to be promoted"
    )
    
    primary_max_failed_subjects = models.IntegerField(
        default=2,
        validators=[MinValueValidator(0)],
        verbose_name="Max Failed Subjects (Primary)",
        help_text="Maximum number of failed subjects allowed for promotion in primary"
    )
    
    # JHS Promotion Rules
    jhs_pass_mark = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=45.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="JHS Pass Mark (%)",
        help_text="Minimum percentage to pass in JHS"
    )
    
    jhs_must_pass_core = models.BooleanField(
        default=True,
        verbose_name="Must Pass Core Subjects (JHS)",
        help_text="Must pass all core subjects (English, Math, Science, Social)"
    )
    
    jhs_max_failed_electives = models.IntegerField(
        default=1,
        validators=[MinValueValidator(0)],
        verbose_name="Max Failed Electives (JHS)",
        help_text="Maximum failed elective subjects allowed in JHS"
    )
    
    # Automatic Promotion Settings
    automatic_promotion_to_p4 = models.BooleanField(
        default=True,
        verbose_name="Automatic Promotion to P4",
        help_text="Automatic promotion from P1-P3 (common in Ghanaian schools)"
    )
    
    require_bnce_for_jhs3 = models.BooleanField(
        default=True,
        verbose_name="Require BNCE for JHS3",
        help_text="Require Basic Education Certificate for JHS3 promotion"
    )
    
    # Remedial Settings
    offer_remedial_classes = models.BooleanField(
        default=True,
        verbose_name="Offer Remedial Classes",
        help_text="Offer remedial classes for struggling students"
    )
    
    remedial_pass_mark = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=50.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Remedial Pass Mark (%)",
        help_text="Minimum percentage to pass remedial assessment"
    )
    
    max_remedial_attempts = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        verbose_name="Max Remedial Attempts",
        help_text="Maximum number of remedial attempts allowed"
    )
    
    # Special Considerations
    allow_conditional_promotion = models.BooleanField(
        default=True,
        verbose_name="Allow Conditional Promotion",
        help_text="Allow conditional promotion with specific requirements"
    )
    
    conditional_promotion_min_attendance = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=75.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Min Attendance for Conditional Promotion (%)",
        help_text="Minimum attendance percentage for conditional promotion"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    
    class Meta:
        verbose_name = "Promotion Configuration"
        verbose_name_plural = "Promotion Configuration"
    
    def __str__(self):
        return f"Promotion Configuration - {self.school_config.school_name}"
    
    @classmethod
    def get_or_create_for_school(cls):
        """Get or create promotion configuration for the school."""
        school_config = SchoolConfiguration.get_config()
        obj, created = cls.objects.get_or_create(school_config=school_config)
        return obj
    
    def get_pass_mark_for_level(self, class_level):
        """Get pass mark for a specific class level."""
        if class_level in ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']:
            return float(self.primary_pass_mark)
        elif class_level in ['J1', 'J2', 'J3']:
            return float(self.jhs_pass_mark)
        else:
            return float(self.school_config.passing_mark)
    
    def can_student_be_promoted(self, student, grades, attendance_percentage):
        """Check if a student can be promoted based on configuration."""
        from core.models.student import Student
        
        if not isinstance(student, Student):
            return False
        
        class_level = student.class_level
        
        # Get appropriate pass mark
        pass_mark = self.get_pass_mark_for_level(class_level)
        
        # Count failed subjects
        failed_subjects = 0
        must_pass_subjects_failed = []
        
        for grade in grades:
            if grade.total_score is None or float(grade.total_score) < pass_mark:
                failed_subjects += 1
                
                # Check if it's a must-pass subject
                if class_level in ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']:
                    if self.primary_must_pass_english and grade.subject.name.lower() == 'english':
                        must_pass_subjects_failed.append('English')
                    if self.primary_must_pass_maths and grade.subject.name.lower() in ['mathematics', 'maths', 'math']:
                        must_pass_subjects_failed.append('Mathematics')
                elif class_level in ['J1', 'J2', 'J3']:
                    if self.jhs_must_pass_core and grade.subject.name.lower() in ['english', 'mathematics', 'maths', 'math', 'science', 'social studies']:
                        must_pass_subjects_failed.append(grade.subject.name)
        
        # Apply promotion rules
        if class_level in ['P1', 'P2', 'P3'] and self.automatic_promotion_to_p4:
            return True, "Automatic promotion for P1-P3"
        
        if must_pass_subjects_failed:
            return False, f"Failed must-pass subjects: {', '.join(must_pass_subjects_failed)}"
        
        if class_level in ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']:
            if failed_subjects > self.primary_max_failed_subjects:
                return False, f"Failed {failed_subjects} subjects (max allowed: {self.primary_max_failed_subjects})"
        
        elif class_level in ['J1', 'J2', 'J3']:
            # For JHS, need more specific logic for core vs electives
            if failed_subjects > (4 + self.jhs_max_failed_electives):  # 4 core subjects + electives
                return False, f"Failed {failed_subjects} subjects"
        
        # Check attendance for conditional promotion
        if self.allow_conditional_promotion and failed_subjects > 0:
            if attendance_percentage < float(self.conditional_promotion_min_attendance):
                return False, f"Low attendance ({attendance_percentage}%) for conditional promotion"
        
        return True, "Eligible for promotion"


class MaintenanceMode(models.Model):
    """Model to track system maintenance mode."""
    is_active = models.BooleanField(default=False, verbose_name="Maintenance Active")
    message = models.TextField(
        blank=True, 
        verbose_name="Maintenance Message",
        help_text="Message to display to users during maintenance"
    )
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="Start Time")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="End Time")
    allowed_ips = models.TextField(
        blank=True, 
        verbose_name="Allowed IPs",
        help_text="Comma-separated list of IPs allowed during maintenance"
    )
    
    # Allow specific users to bypass maintenance mode
    allowed_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='maintenance_bypass_users',
        verbose_name="Allowed Users",
        help_text="Users who can access the system during maintenance"
    )
    
    # Allow all staff users to bypass
    allow_staff_access = models.BooleanField(
        default=True,
        verbose_name="Allow Staff Access",
        help_text="Allow all staff users to access the system during maintenance"
    )
    
    # Allow all superusers to bypass  
    allow_superuser_access = models.BooleanField(
        default=True,
        verbose_name="Allow Superuser Access",
        help_text="Allow all superusers to access the system during maintenance"
    )
    
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        verbose_name="Created By"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    
    class Meta:
        verbose_name = 'Maintenance Mode'
        verbose_name_plural = 'Maintenance Mode'
    
    def __str__(self):
        return f"Maintenance Mode - {'Active' if self.is_active else 'Inactive'}"
    
    def is_currently_active(self):
        """Check if maintenance is currently active based on time window."""
        if not self.is_active:
            return False
        
        now = timezone.now()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
            
        return True
    
    def can_user_bypass(self, user):
        """Check if user can bypass maintenance mode."""
        if not user or not user.is_authenticated:
            return False
            
        # Superusers can always bypass if allowed
        if self.allow_superuser_access and user.is_superuser:
            return True
            
        # Staff users can bypass if allowed
        if self.allow_staff_access and user.is_staff:
            return True
            
        # Specific allowed users can bypass
        if self.allowed_users.filter(id=user.id).exists():
            return True
            
        return False
    
    @classmethod
    def get_current_maintenance(cls):
        """Get the current maintenance mode instance."""
        return cls.objects.filter(is_active=True).first()
    
    @classmethod
    def can_user_access(cls, user):
        """Check if user can access the system (bypass maintenance)."""
        maintenance = cls.get_current_maintenance()
        
        # No active maintenance - everyone can access
        if not maintenance or not maintenance.is_currently_active():
            return True
            
        # Check if user can bypass maintenance
        return maintenance.can_user_bypass(user)


class ScheduledMaintenance(models.Model):
    """Model for scheduled maintenance windows."""
    
    MAINTENANCE_TYPES = [
        ('EMERGENCY', 'Emergency Maintenance'),
        ('SCHEDULED', 'Scheduled Maintenance'),
        ('UPGRADE', 'System Upgrade'),
        ('BACKUP', 'System Backup'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="Maintenance Title")
    description = models.TextField(blank=True, verbose_name="Description")
    maintenance_type = models.CharField(
        max_length=20, 
        choices=MAINTENANCE_TYPES, 
        default='SCHEDULED',
        verbose_name="Maintenance Type"
    )
    start_time = models.DateTimeField(verbose_name="Start Time")
    end_time = models.DateTimeField(verbose_name="End Time")
    message = models.TextField(
        verbose_name="User Message",
        help_text="Message to display to users during maintenance"
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")
    was_executed = models.BooleanField(default=False, verbose_name="Was Executed")
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        verbose_name="Created By"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    
    class Meta:
        verbose_name = 'Scheduled Maintenance'
        verbose_name_plural = 'Scheduled Maintenance'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.title} ({self.start_time} to {self.end_time})"
    
    def is_currently_active(self):
        """Check if maintenance is currently active."""
        now = timezone.now()
        return self.start_time <= now <= self.end_time and self.is_active
    
    def is_upcoming(self):
        """Check if maintenance is upcoming."""
        return self.start_time > timezone.now() and self.is_active
    
    def is_past(self):
        """Check if maintenance is in the past."""
        return self.end_time < timezone.now()
    
    def duration(self):
        """Calculate maintenance duration."""
        return self.end_time - self.start_time
    
    def get_status(self):
        """Get maintenance status."""
        if not self.is_active:
            return 'CANCELLED'
        elif self.is_past():
            return 'COMPLETED'
        elif self.is_currently_active():
            return 'IN_PROGRESS'
        elif self.is_upcoming():
            return 'UPCOMING'
        else:
            return 'UNKNOWN'


    
    