# core/models/assignments.py - FIXED VERSION
"""
Assignment management models.
"""
import logging
from datetime import date, timedelta  # Added date and timedelta
from django.db import models, transaction
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.db.models import Avg, Sum, Count

from core.models.base import CLASS_LEVEL_CHOICES
# CHANGE THESE IMPORTS:
# OLD: from core.models.academic import Subject, ClassAssignment
# NEW: Import from separate files
from core.models.subject import Subject
from core.models.class_assignment import ClassAssignment
from core.models.student import Student
from core.models.teacher import Teacher

logger = logging.getLogger(__name__)


class Assignment(models.Model):
    ASSIGNMENT_TYPES = [
        ('HOMEWORK', 'Homework'),
        ('CLASSWORK', 'Classwork'),
        ('TEST', 'Test'),
        ('EXAM', 'Examination'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUBMITTED', 'Submitted'),
        ('LATE', 'Late'),
        ('GRADED', 'Graded'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assignment_type = models.CharField(max_length=10, choices=ASSIGNMENT_TYPES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_assignment = models.ForeignKey(ClassAssignment, on_delete=models.CASCADE)
    due_date = models.DateTimeField()
    max_score = models.PositiveSmallIntegerField(default=100)
    weight = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Percentage weight of this assignment in the final grade"
    )
    attachment = models.FileField(
        upload_to='assignment_attachments/', 
        blank=True, 
        null=True,
        help_text="Assignment document/attachment"
    )
    
    # Additional fields for enhanced assignment management
    instructions = models.TextField(blank=True, help_text="Detailed assignment instructions")
    learning_objectives = models.TextField(blank=True, help_text="What students will learn")
    resources = models.TextField(blank=True, help_text="Recommended resources/links")
    rubric = models.FileField(upload_to='assignment_rubrics/', blank=True, null=True)
    sample_solution = models.FileField(upload_to='sample_solutions/', blank=True, null=True)
    
    allow_late_submissions = models.BooleanField(
        default=False,
        help_text="Allow students to submit after the due date"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date', 'subject']
        verbose_name = 'Assignment'
        verbose_name_plural = 'Assignments'
    
    def __str__(self):
        return f"{self.get_assignment_type_display()} - {self.subject} ({self.class_assignment.get_class_level_display()})"
    
    @property
    def has_valid_attachment(self):
        """Check if assignment has a valid attachment"""
        if not self.attachment:
            return False
        
        return hasattr(self.attachment, 'name') and bool(self.attachment.name.strip())
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        # Ensure subject is set if we have class_assignment
        if self.class_assignment and not self.subject_id:
            self.subject = self.class_assignment.subject
        
        # Validate subject is required
        if not self.subject_id:
            raise ValidationError({'subject': 'Subject is required'})
        
        # Validate subject matches class_assignment
        if (self.class_assignment and self.subject_id and 
            self.class_assignment.subject_id != self.subject_id):
            raise ValidationError({
                'subject': f'Subject must match class assignment subject ({self.class_assignment.subject.name})'
            })
        
        # Validate attachment is not an empty string
        if hasattr(self, 'attachment') and self.attachment == '':
            raise ValidationError({
                'attachment': 'Attachment cannot be empty. Please select a file or leave it blank.'
            })
    
    def save(self, *args, **kwargs):
        """Save assignment with automatic subject setting and attachment fixes"""
        is_new = self.pk is None
        
        # Fix Django's empty string issue for NULL FileFields
        if hasattr(self, 'attachment') and self.attachment == '':
            self.attachment = None
        
        # Auto-set subject from class_assignment
        if self.class_assignment and not self.subject_id:
            self.subject = self.class_assignment.subject
            logger.info(f"Auto-set subject to {self.subject.name} from class_assignment")
        
        # Double-check subject is set
        if not self.subject_id:
            raise ValidationError({
                'subject': 'Subject is required. Either set subject directly or provide a class_assignment.'
            })
        
        # Clear any cached attachment property
        if hasattr(self, '_attachment_cache'):
            delattr(self, '_attachment_cache')
        
        # Call parent save
        super().save(*args, **kwargs)
        
        # Create student assignments for new assignments
        if is_new:
            transaction.on_commit(lambda: self.create_student_assignments())
    
    def create_student_assignments(self):
        """Create StudentAssignment records for all students in the class"""
        try:
            students = Student.objects.filter(
                class_level=self.class_assignment.class_level,
                is_active=True
            )
            
            student_assignments = []
            for student in students:
                if not StudentAssignment.objects.filter(
                    student=student, 
                    assignment=self
                ).exists():
                    student_assignments.append(
                        StudentAssignment(
                            student=student,
                            assignment=self,
                            status='PENDING'
                        )
                    )
            
            if student_assignments:
                StudentAssignment.objects.bulk_create(student_assignments)
                logger.info(f"Created {len(student_assignments)} student assignments for assignment {self.id}")
                
        except Exception as e:
            logger.error(f"Error creating student assignments for assignment {self.id}: {str(e)}")
    
    def get_analytics(self, recalculate=False):
        """Get or calculate assignment analytics"""
        analytics, created = AssignmentAnalytics.objects.get_or_create(
            assignment=self
        )
        
        if created or recalculate or not analytics.last_calculated:
            analytics.calculate_analytics()
            
        return analytics
    
    def get_quick_stats(self):
        """Get quick statistics for the assignment"""
        student_assignments = self.student_assignments.all()
            
        return {
            'total_students': student_assignments.count(),
            'submitted': student_assignments.exclude(status='PENDING').count(),
            'graded': student_assignments.filter(status='GRADED').count(),
            'pending': student_assignments.filter(status='PENDING').count(),
        }
    
    def get_student_assignment(self, student):
        """Get or create StudentAssignment for a specific student"""
        student_assignment, created = StudentAssignment.objects.get_or_create(
            assignment=self,
            student=student,
            defaults={'status': 'PENDING'}
        )
        return student_assignment
    
    def can_student_submit(self, student):
        """Check if student can submit this assignment"""
        if not self.is_active:
            return False, "This assignment is no longer active"
        
        student_assignment = self.get_student_assignment(student)
        
        if student_assignment.status == 'GRADED':
            return False, "Assignment has already been graded"
        
        if self.due_date < timezone.now() and not self.allow_late_submissions:
            return False, "Assignment due date has passed and late submissions are not allowed"
        
        return True, "Can submit"
    
    def get_status_summary(self):
        """Get comprehensive status summary"""
        student_assignments = self.student_assignments.all()
        
        return {
            'total': student_assignments.count(),
            'pending': student_assignments.filter(status='PENDING').count(),
            'submitted': student_assignments.filter(status='SUBMITTED').count(),
            'late': student_assignments.filter(status='LATE').count(),
            'graded': student_assignments.filter(status='GRADED').count(),
        }
    
    def get_completion_percentage(self):
        """Calculate completion percentage"""
        summary = self.get_status_summary()
        total = summary['total']
        if total == 0:
            return 0
        
        completed = summary['submitted'] + summary['late'] + summary['graded']
        return round((completed / total) * 100, 1)
    
    def is_overdue(self):
        """Check if assignment is overdue"""
        return self.due_date < timezone.now()


class StudentAssignment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='student_assignments')
    status = models.CharField(max_length=10, choices=Assignment.STATUS_CHOICES, default='PENDING')
    submitted_date = models.DateTimeField(null=True, blank=True)
    
    # Enhanced functionality fields
    graded_date = models.DateTimeField(null=True, blank=True)
    feedback_document = models.FileField(upload_to='assignment_feedback/', blank=True, null=True)
    teacher_comments = models.TextField(blank=True)
    rubric_score = models.JSONField(null=True, blank=True, help_text="JSON structure for rubric-based scoring")
    is_draft = models.BooleanField(default=False, help_text="Flag for draft submissions")
    last_viewed_by_student = models.DateTimeField(null=True, blank=True)
    last_viewed_by_teacher = models.DateTimeField(null=True, blank=True)
    
    # Existing fields
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    file = models.FileField(upload_to='assignments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'assignment')
        ordering = ['assignment__due_date', 'student']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['submitted_date']),
            models.Index(fields=['graded_date']),
            models.Index(fields=['score']),
            models.Index(fields=['assignment', 'student']),
            models.Index(fields=['student', 'status']),
            models.Index(fields=['assignment', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]
        verbose_name = 'Student Assignment'
        verbose_name_plural = 'Student Assignments'
    
    def __str__(self):
        return f"{self.student} - {self.assignment.title} ({self.status})"
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        # Validate score is within assignment max_score
        if self.score is not None and self.assignment:
            if self.score > self.assignment.max_score:
                raise ValidationError({
                    'score': f'Score cannot exceed maximum score of {self.assignment.max_score}'
                })
            if self.score < 0:
                raise ValidationError({
                    'score': 'Score cannot be negative'
                })
        
        # Validate that submitted date is not in the future
        if self.submitted_date and self.submitted_date > timezone.now():
            raise ValidationError({
                'submitted_date': 'Submission date cannot be in the future'
            })
    
    def save(self, *args, **kwargs):
        """Save with automatic status management"""
        # Fix Django's empty string issue for FileFields
        if hasattr(self, 'file') and self.file == '':
            self.file = None
        if hasattr(self, 'feedback_document') and self.feedback_document == '':
            self.feedback_document = None
        
        # Auto-set graded_date when status changes to GRADED
        if self.status == 'GRADED' and not self.graded_date:
            self.graded_date = timezone.now()
        
        # Auto-set status based on submission date
        if self.submitted_date and not self.status == 'GRADED':
            if self.is_late():
                self.status = 'LATE'
            else:
                self.status = 'SUBMITTED'
        
        # If score is set, automatically mark as graded
        if self.score is not None and self.status != 'GRADED':
            self.status = 'GRADED'
            if not self.graded_date:
                self.graded_date = timezone.now()
        
        # Clear any cached file properties
        if hasattr(self, '_file_cache'):
            delattr(self, '_file_cache')
        if hasattr(self, '_feedback_document_cache'):
            delattr(self, '_feedback_document_cache')
        
        super().save(*args, **kwargs)
    
    @property
    def has_valid_file(self):
        """Check if student has uploaded a valid file"""
        if not self.file:
            return False
        return hasattr(self.file, 'name') and bool(self.file.name.strip())
    
    @property
    def has_feedback_document(self):
        """Check if teacher has uploaded feedback document"""
        if not self.feedback_document:
            return False
        return hasattr(self.feedback_document, 'name') and bool(self.feedback_document.name.strip())
    
    def get_submission_status_display(self):
        """Get a human-readable status with icons/colors"""
        status_map = {
            'PENDING': {'icon': '🔴', 'text': 'Pending', 'color': 'danger', 'class': 'badge-danger'},
            'SUBMITTED': {'icon': '🟡', 'text': 'Submitted', 'color': 'warning', 'class': 'badge-warning'},
            'LATE': {'icon': '🟠', 'text': 'Late', 'color': 'warning', 'class': 'badge-warning'},
            'GRADED': {'icon': '🟢', 'text': 'Graded', 'color': 'success', 'class': 'badge-success'},
        }
        return status_map.get(self.status, {'icon': '⚪', 'text': 'Unknown', 'color': 'secondary', 'class': 'badge-secondary'})
    
    def get_time_remaining_display(self):
        """Get human-readable time remaining"""
        if self.status == 'GRADED':
            return "Completed"
        
        now = timezone.now()
        if self.assignment.due_date < now:
            days_late = (now - self.assignment.due_date).days
            return f"{days_late} day(s) overdue"
        
        time_remaining = self.assignment.due_date - now
        
        if time_remaining.days > 0:
            return f"{time_remaining.days} day(s) remaining"
        elif time_remaining.seconds // 3600 > 0:
            hours = time_remaining.seconds // 3600
            return f"{hours} hour(s) remaining"
        else:
            minutes = (time_remaining.seconds % 3600) // 60
            return f"{minutes} minute(s) remaining"
    
    def is_late(self):
        """Check if submission is late"""
        if self.submitted_date and self.assignment.due_date:
            return self.submitted_date > self.assignment.due_date
        return False
    
    def is_overdue(self):
        """Check if assignment is overdue (not submitted and past due date)"""
        if self.status in ['SUBMITTED', 'LATE', 'GRADED']:
            return False
        return self.assignment.due_date < timezone.now()
    
    def get_assignment_document_url(self):
        """Get URL for teacher's assignment document"""
        if self.assignment and self.assignment.has_valid_attachment:
            return self.assignment.attachment.url
        return None
    
    def can_student_submit_work(self):
        """Check if student can still submit work"""
        if self.status in ['GRADED']:
            return (False, "Assignment has already been graded")
        
        if not self.assignment.is_active:
            return (False, "This assignment is no longer active")
        
        now = timezone.now()
        if self.assignment.due_date < now:
            if not self.assignment.allow_late_submissions:
                return (False, "Late submissions are not allowed")
            return (True, "Can submit late (penalty may apply)")
        
        return (True, "Can submit")
    
    def can_view_feedback(self):
        """Check if student can view feedback"""
        return self.status == 'GRADED' and (
            self.score is not None or 
            self.feedback or 
            self.teacher_comments or 
            self.has_feedback_document
        )
    
    @property
    def can_student_submit(self):
        """Property version for template access"""
        can_submit, _ = self.can_student_submit_work()
        return can_submit
    
    def submit_student_work(self, file, feedback="", is_draft=False):
        """Submit student work with validation"""
        can_submit, message = self.can_student_submit_work()
        if not can_submit:
            raise ValidationError(message)
        
        self.file = file
        self.feedback = feedback
        self.submitted_date = timezone.now()
        self.is_draft = is_draft
        
        # Check if submission is late
        if self.submitted_date > self.assignment.due_date:
            self.status = 'LATE'
        else:
            self.status = 'SUBMITTED'
        
        self.save()
        return True
    
    def submit_draft(self, file, feedback=""):
        """Submit a draft version"""
        return self.submit_student_work(file, feedback, is_draft=True)
    
    def get_feedback_document_url(self):
        """Get URL for teacher's feedback/graded document"""
        if self.has_feedback_document:
            return self.feedback_document.url
        return None
    
    def get_score_percentage(self):
        """Calculate score percentage"""
        if self.score is None or self.assignment.max_score == 0:
            return 0
        return (self.score / self.assignment.max_score) * 100
    
    def get_grade_letter(self):
        """Get letter grade based on percentage"""
        percentage = self.get_score_percentage()
        
        if percentage >= 90:
            return "A+"
        elif percentage >= 85:
            return "A"
        elif percentage >= 80:
            return "A-"
        elif percentage >= 75:
            return "B+"
        elif percentage >= 70:
            return "B"
        elif percentage >= 65:
            return "C+"
        elif percentage >= 60:
            return "C"
        elif percentage >= 55:
            return "D+"
        elif percentage >= 50:
            return "D"
        else:
            return "F"
    
    def get_progress_status(self):
        """Get progress status for visualization"""
        if self.status == 'PENDING':
            return {'percentage': 25, 'label': 'Not Started', 'color': 'danger', 'class': 'bg-danger'}
        elif self.status == 'SUBMITTED':
            return {'percentage': 75, 'label': 'Submitted', 'color': 'warning', 'class': 'bg-warning'}
        elif self.status == 'LATE':
            return {'percentage': 50, 'label': 'Late Submission', 'color': 'warning', 'class': 'bg-warning'}
        elif self.status == 'GRADED':
            return {'percentage': 100, 'label': 'Graded', 'color': 'success', 'class': 'bg-success'}
        return {'percentage': 0, 'label': 'Unknown', 'color': 'secondary', 'class': 'bg-secondary'}
    
    def mark_as_viewed_by_student(self):
        """Mark as viewed by student"""
        self.last_viewed_by_student = timezone.now()
        self.save(update_fields=['last_viewed_by_student', 'updated_at'])
    
    def mark_as_viewed_by_teacher(self):
        """Mark as viewed by teacher"""
        self.last_viewed_by_teacher = timezone.now()
        self.save(update_fields=['last_viewed_by_teacher', 'updated_at'])
    
    def has_unseen_feedback(self, user_type='student'):
        """Check if there's unseen feedback for student or teacher"""
        if user_type == 'student':
            return self.status == 'GRADED' and (
                (self.last_viewed_by_student is None) or 
                (self.graded_date and self.graded_date > self.last_viewed_by_student)
            )
        elif user_type == 'teacher':
            return self.submitted_date and (
                (self.last_viewed_by_teacher is None) or 
                (self.submitted_date > self.last_viewed_by_teacher)
            )
        return False
    
    def get_priority_level(self):
        """Get priority level for teacher grading"""
        now = timezone.now()
        
        if self.status == 'GRADED':
            return "completed"
        elif self.status == 'SUBMITTED' or self.status == 'LATE':
            days_since_submission = (now - self.submitted_date).days if self.submitted_date else 0
            if days_since_submission > 7:
                return "high"
            elif days_since_submission > 3:
                return "medium"
            else:
                return "low"
        elif self.is_overdue():
            return "urgent"
        elif self.assignment.due_date <= now + timedelta(days=1):
            return "high"
        elif self.assignment.due_date <= now + timedelta(days=3):
            return "medium"
        else:
            return "low"
    
    def can_be_regraded(self):
        """Check if assignment can be regraded"""
        return self.status == 'GRADED' and self.graded_date and (timezone.now() - self.graded_date).days <= 7
    
    @classmethod
    def get_statistics_for_student(cls, student):
        """Get comprehensive statistics for a student"""
        assignments = cls.objects.filter(student=student)
        
        total_count = assignments.count()
        if total_count == 0:
            return {
                'total': 0,
                'pending': 0,
                'submitted': 0,
                'graded': 0,
                'late': 0,
                'overdue': 0,
                'average_score': 0,
                'submission_rate': 0,
                'timely_submission_rate': 0,
                'completion_rate': 0
            }
        
        pending_count = assignments.filter(status='PENDING').count()
        submitted_count = assignments.filter(status__in=['SUBMITTED', 'LATE']).count()
        graded_count = assignments.filter(status='GRADED').count()
        late_count = assignments.filter(status='LATE').count()
        overdue_count = len([a for a in assignments if a.is_overdue()])
        
        avg_score = assignments.filter(score__isnull=False).aggregate(Avg('score'))['score__avg'] or 0
        submission_rate = (submitted_count / total_count * 100) if total_count > 0 else 0
        timely_submission_rate = (assignments.filter(status='SUBMITTED').count() / total_count * 100) if total_count > 0 else 0
        completion_rate = (graded_count / total_count * 100) if total_count > 0 else 0
        
        return {
            'total': total_count,
            'pending': pending_count,
            'submitted': submitted_count,
            'graded': graded_count,
            'late': late_count,
            'overdue': overdue_count,
            'average_score': round(avg_score, 2),
            'submission_rate': round(submission_rate, 1),
            'timely_submission_rate': round(timely_submission_rate, 1),
            'completion_rate': round(completion_rate, 1)
        }
    
    @property
    def formatted_score(self):
        """Get formatted score with percentage"""
        if self.score is None:
            return "Not graded"
        
        percentage = self.get_score_percentage()
        return f"{self.score}/{self.assignment.max_score} ({percentage:.1f}%)"
    
    @property
    def days_late(self):
        """Get number of days late if applicable"""
        if self.submitted_date and self.assignment.due_date:
            if self.submitted_date > self.assignment.due_date:
                return (self.submitted_date - self.assignment.due_date).days
        return 0
    
    def update_score(self, score, feedback="", teacher_comments="", feedback_document=None):
        """Update score and related feedback"""
        if not self.assignment.is_active:
            raise ValidationError("Cannot grade an inactive assignment")
        
        if score < 0 or score > self.assignment.max_score:
            raise ValidationError(f"Score must be between 0 and {self.assignment.max_score}")
        
        self.score = score
        self.feedback = feedback
        self.teacher_comments = teacher_comments
        self.status = 'GRADED'
        self.graded_date = timezone.now()
        
        if feedback_document:
            self.feedback_document = feedback_document
        
        self.save()


class AssignmentAnalytics(models.Model):
    """Model to track assignment analytics and statistics"""
    assignment = models.OneToOneField(
        Assignment, 
        on_delete=models.CASCADE, 
        related_name='analytics'
    )
    average_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    highest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lowest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    submission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    on_time_submission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    total_students = models.PositiveIntegerField(default=0)
    graded_students = models.PositiveIntegerField(default=0)
    pending_students = models.PositiveIntegerField(default=0)
    late_submissions = models.PositiveIntegerField(default=0)
    last_calculated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Assignment Analytics'
        verbose_name_plural = 'Assignment Analytics'
        ordering = ['-last_calculated']
    
    def __str__(self):
        return f"Analytics for {self.assignment.title}"
    
    def calculate_analytics(self):
        """Calculate and update analytics data with error handling"""
        try:
            student_assignments = self.assignment.student_assignments.all()
            self.total_students = student_assignments.count()
            
            # Count students by status
            self.pending_students = student_assignments.filter(status='PENDING').count()
            self.graded_students = student_assignments.filter(status='GRADED').count()
            self.late_submissions = student_assignments.filter(status='LATE').count()
            
            # Calculate score statistics
            graded_with_scores = student_assignments.filter(
                status='GRADED', 
                score__isnull=False
            )
            
            if graded_with_scores.exists():
                scores = [float(sa.score) for sa in graded_with_scores]
                self.average_score = sum(scores) / len(scores)
                self.highest_score = max(scores)
                self.lowest_score = min(scores)
            else:
                self.average_score = None
                self.highest_score = None
                self.lowest_score = None
            
            # Calculate submission rates
            submitted_assignments = student_assignments.exclude(status='PENDING')
            on_time_assignments = student_assignments.filter(
                status__in=['SUBMITTED', 'GRADED'],
                submitted_date__lte=self.assignment.due_date
            ) if self.assignment.due_date else submitted_assignments
            
            if self.total_students > 0:
                self.submission_rate = (submitted_assignments.count() / self.total_students) * 100
                self.on_time_submission_rate = (on_time_assignments.count() / self.total_students) * 100
            
            self.save()
            return True
            
        except Exception as e:
            logger.error(f"Error calculating analytics for assignment {self.assignment.id}: {str(e)}")
            return False
    
    def get_status_summary(self):
        """Get summary of assignment statuses"""
        return {
            'total': self.total_students,
            'pending': self.pending_students,
            'graded': self.graded_students,
            'late': self.late_submissions,
            'submitted': self.total_students - self.pending_students
        }


class AssignmentTemplate(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    assignment_type = models.CharField(max_length=10, choices=Assignment.ASSIGNMENT_TYPES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    max_score = models.PositiveSmallIntegerField(default=100)
    weight = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    attachment = models.FileField(upload_to='assignment_templates/', blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Assignment Template'
        verbose_name_plural = 'Assignment Templates'
    
    def create_assignment_from_template(self, class_levels, due_date):
        """Create actual assignments from this template"""
        assignments = []
        for class_level in class_levels:
            class_assignment = ClassAssignment.objects.filter(
                class_level=class_level,
                subject=self.subject
            ).first()
            
            if class_assignment:
                assignment = Assignment.objects.create(
                    title=self.title,
                    description=self.description,
                    assignment_type=self.assignment_type,
                    subject=self.subject,
                    class_assignment=class_assignment,
                    due_date=due_date,
                    max_score=self.max_score,
                    weight=self.weight,
                    attachment=self.attachment
                )
                assignments.append(assignment)
        
        return assignments