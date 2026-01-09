# core/models/report_card.py - UPDATED VERSION
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone

# CHANGE THIS IMPORT:
# OLD: from core.models.academic import AcademicTerm
# NEW: Import from academic_term instead
from core.models.academic_term import AcademicTerm

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
    
    # Use AcademicTerm from academic_term.py
    academic_term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Academic Period",
        help_text="Link to academic period (optional)"
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
    subjects_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of subjects graded"
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
            models.Index(fields=['academic_term']),
        ]
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.academic_year} Term {self.term}"
    
    def save(self, *args, **kwargs):
        """Calculate grades if not already calculated"""
        is_new = self.pk is None
        
        # Try to link to AcademicTerm if not set
        if not self.academic_term and self.academic_year and self.term:
            try:
                academic_term = AcademicTerm.objects.filter(
                    academic_year__name=self.academic_year,  # Changed from academic_year to academic_year__name
                    period_system='TERM',
                    period_number=self.term
                ).first()
                if academic_term:
                    self.academic_term = academic_term
            except Exception:
                pass
        
        # Ensure we always have a grade (CRITICAL FIX)
        if not self.overall_grade or self.overall_grade == '':
            self.calculate_grades()
        
        # Double-check: NEVER allow empty grades
        if not self.overall_grade or self.overall_grade == '':
            if self.average_score and float(self.average_score) > 0:
                score = float(self.average_score)
                if score >= 90:
                    self.overall_grade = 'A+'
                elif score >= 80:
                    self.overall_grade = 'A'
                elif score >= 70:
                    self.overall_grade = 'B+'
                elif score >= 60:
                    self.overall_grade = 'B'
                elif score >= 50:
                    self.overall_grade = 'C+'
                elif score >= 40:
                    self.overall_grade = 'C'
                elif score >= 30:
                    self.overall_grade = 'D+'
                elif score >= 20:
                    self.overall_grade = 'D'
                else:
                    self.overall_grade = 'E'
            else:
                self.overall_grade = 'E'  # Default to E, NEVER empty!
        
        super().save(*args, **kwargs)
        
        # For new report cards, also create/update related objects
        if is_new:
            self.update_related_data()

    def calculate_grades(self):
        """Calculate average score and overall grade from student's grades"""
        try:
            # Dynamic import to avoid circular dependencies
            from django.apps import apps
        
            # Get Grade model
            GradeModel = apps.get_model('core', 'Grade')
        
            # Get grades for this student and term
            grades = GradeModel.objects.filter(
                student=self.student,
                academic_year=self.academic_year,
                term=self.term
            )
        
            if grades.exists():
                # Calculate average of total scores
                total_scores = []
                for grade in grades:
                    if grade.total_score is not None:
                        try:
                            total_scores.append(float(grade.total_score))
                        except (ValueError, TypeError):
                            continue
            
                if total_scores:
                    # Calculate average
                    average = sum(total_scores) / len(total_scores)
                    self.average_score = Decimal(str(average)).quantize(Decimal('0.01'))
                    self.subjects_count = len(total_scores)
                
                    # Determine overall grade
                    try:
                        from core.models.configuration import SchoolConfiguration
                        config = SchoolConfiguration.get_config()
                        self.overall_grade = config.get_letter_grade_for_score(self.average_score)
                    except Exception as config_error:
                        # Fallback calculation - NEVER return empty string
                        self.overall_grade = self.calculate_grade(self.average_score)
                    
                        # Ensure it's not empty
                        if not self.overall_grade or self.overall_grade == '':
                            self.overall_grade = 'E'
                else:
                    self.average_score = Decimal('0.00')
                    self.subjects_count = 0
                    self.overall_grade = 'E'  # Default to E, NOT empty!
            else:
                self.average_score = Decimal('0.00')
                self.subjects_count = 0
                self.overall_grade = 'E'  # Default to E, NOT empty!
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in calculate_grades for report card: {e}")
            self.average_score = Decimal('0.00')
            self.subjects_count = 0
            self.overall_grade = 'E'  # Default to E, NOT empty!
    
    @staticmethod
    def calculate_grade(score):
        """Calculate letter grade based on score"""
        if score is None:
            return ''
            
        try:
            score = float(score)
            if score >= 90:
                return 'A+'
            elif score >= 80:
                return 'A'
            elif score >= 70:
                return 'B+'
            elif score >= 60:
                return 'B'
            elif score >= 50:
                return 'C+'
            elif score >= 40:
                return 'C'
            elif score >= 30:
                return 'D+'
            elif score >= 20:
                return 'D'
            else:
                return 'E'
        except (ValueError, TypeError):
            return ''
    
    def get_absolute_url(self):
        """Get URL for viewing this report card"""
        try:
            return reverse('report_card_detail', kwargs={
                'student_id': self.student.id,
                'report_card_id': self.id
            })
        except:
            return f'/report-card/{self.student.id}/detail/{self.id}/'
    
    def get_pdf_url(self):
        """Get URL for PDF version"""
        try:
            return reverse('report_card_pdf_detail', kwargs={
                'student_id': self.student.id,
                'report_card_id': self.id
            })
        except:
            return f'/report-card/{self.student.id}/pdf/{self.id}/'
    
    def get_edit_url(self):
        """Get URL for editing grades"""
        try:
            return reverse('grade_edit', kwargs={'pk': self.id})
        except:
            return f'/grades/{self.id}/edit/'
    
    def can_user_access(self, user):
        """Check if user has permission to view this report card"""
        try:
            if user.is_superuser or user.is_staff:
                return True
            
            if hasattr(user, 'student') and user.student == self.student:
                return True
            
            if hasattr(user, 'teacher'):
                from django.apps import apps
                ClassAssignment = apps.get_model('core', 'ClassAssignment')
                return ClassAssignment.objects.filter(
                    class_level=self.student.class_level,
                    teacher=user.teacher
                ).exists()
            
            if hasattr(user, 'parentguardian'):
                return self.student in user.parentguardian.students.all()
            
            return False
        except:
            return False
    
    def get_performance_level(self):
        """Get performance level description"""
        try:
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
        except (ValueError, TypeError):
            return 'No Data'
    
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
            self.created_by = user
        self.save()
        return self
    
    def unpublish(self, user=None):
        """Unpublish the report card"""
        self.is_published = False
        self.save()
        return self
    
    def update_related_data(self):
        """Update related analytics or cache data"""
        # You can add logic here to update analytics cache, etc.
        pass
    
    def get_grades_summary(self):
        """Get summary of all grades for this report card"""
        try:
            from django.apps import apps
            Grade = apps.get_model('core', 'Grade')
            
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
                        'grade': grade.letter_grade or '',
                        'teacher': grade.recorded_by.get_full_name() if grade.recorded_by else 'N/A'
                    }
                    for grade in grades
                ]
            }
        except:
            return {'total_subjects': 0, 'grades_list': []}
    
    def get_attendance_summary(self):
        """Get attendance summary"""
        try:
            from django.apps import apps
            from django.db.models import Q
            from core.models import StudentAttendance, AcademicTerm
            
            # Find the academic term
            term_obj = AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                term=self.term
            ).first()
            
            if not term_obj:
                return {
                    'present_days': 0,
                    'total_days': 0,
                    'attendance_rate': 0.0,
                    'absence_count': 0,
                    'attendance_status': 'No Term Data',
                    'is_ges_compliant': False
                }
            
            # Get attendance records
            attendance_records = StudentAttendance.objects.filter(
                student=self.student,
                term=term_obj
            )
            
            total_days = attendance_records.count()
            
            if total_days > 0:
                present_days = attendance_records.filter(
                    Q(status='present') | Q(status='late') | Q(status='excused')
                ).count()
                attendance_rate = (present_days / total_days) * 100
                is_ges_compliant = attendance_rate >= 75.0
                
                # Determine status
                if attendance_rate >= 90:
                    attendance_status = "Excellent"
                elif attendance_rate >= 80:
                    attendance_status = "Good"
                elif attendance_rate >= 70:
                    attendance_status = "Satisfactory"
                elif attendance_rate >= 60:
                    attendance_status = "Needs Improvement"
                else:
                    attendance_status = "Unsatisfactory"
            else:
                present_days = 0
                attendance_rate = 0.0
                is_ges_compliant = False
                attendance_status = "No Data"
            
            return {
                'present_days': present_days,
                'total_days': total_days,
                'attendance_rate': round(attendance_rate, 1),
                'absence_count': total_days - present_days,
                'attendance_status': attendance_status,
                'is_ges_compliant': is_ges_compliant
            }
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting attendance summary: {e}")
            return {
                'present_days': 0,
                'total_days': 0,
                'attendance_rate': 0.0,
                'absence_count': 0,
                'attendance_status': 'Error',
                'is_ges_compliant': False
            }
    
    def get_position_in_class(self):
        """Calculate student's position in class"""
        try:
            from django.apps import apps
            from django.db.models import Avg
            from core.models import Student, Grade
            
            # Get all students in same class
            classmates = Student.objects.filter(
                class_level=self.student.class_level,
                is_active=True
            )
            
            # Calculate average scores for all students
            student_scores = []
            for student in classmates:
                grades = Grade.objects.filter(
                    student=student,
                    academic_year=self.academic_year,
                    term=self.term
                )
                
                if grades.exists():
                    avg_score = grades.aggregate(avg=Avg('total_score'))['avg'] or 0
                else:
                    avg_score = 0
                
                student_scores.append({
                    'student_id': student.id,
                    'average': float(avg_score)
                })
            
            # Sort by average score (descending)
            student_scores.sort(key=lambda x: x['average'], reverse=True)
            
            # Find this student's position
            for index, score_data in enumerate(student_scores, 1):
                if score_data['student_id'] == self.student.id:
                    total_students = len(student_scores)
                    
                    # Format position with ordinal
                    if index == 1:
                        ordinal = "1st"
                    elif index == 2:
                        ordinal = "2nd"
                    elif index == 3:
                        ordinal = "3rd"
                    else:
                        ordinal = f"{index}th"
                    
                    return f"{ordinal} of {total_students}"
            
            return "Not ranked"
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating position in class: {e}")
            return "Not available"
    
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
    
    @property
    def is_passing(self):
        """Check if overall grade is passing (C or better)"""
        passing_grades = ['A+', 'A', 'B+', 'B', 'C+', 'C']
        return self.overall_grade in passing_grades
    
    @property
    def performance_icon(self):
        """Get performance icon"""
        try:
            score = float(self.average_score)
            if score >= 80:
                return 'fas fa-trophy text-success'
            elif score >= 70:
                return 'fas fa-star text-info'
            elif score >= 60:
                return 'fas fa-check-circle text-primary'
            elif score >= 50:
                return 'fas fa-exclamation-circle text-warning'
            else:
                return 'fas fa-times-circle text-danger'
        except:
            return 'fas fa-question-circle text-secondary'