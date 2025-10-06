# core/management/commands/send_assignment_reminders.py
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from core.models import StudentAssignment

class Command(BaseCommand):
    help = 'Send assignment due date reminders to students'
    
    def handle(self, *args, **options):
        tomorrow = timezone.now() + timedelta(days=1)
        upcoming_assignments = StudentAssignment.objects.filter(
            assignment__due_date__date=tomorrow.date(),
            status__in=['PENDING', 'LATE']
        ).select_related('student', 'assignment')
        
        for student_assignment in upcoming_assignments:
            self.send_reminder(student_assignment)
        
        self.stdout.write(
            self.style.SUCCESS(f"Sent {upcoming_assignments.count()} reminders")
        )
    
    def send_reminder(self, student_assignment):
        student = student_assignment.student
        assignment = student_assignment.assignment
        
        subject = f"Reminder: {assignment.title} due tomorrow"
        message = f"""
        Hi {student.get_full_name()},
        
        This is a reminder that your assignment "{assignment.title}" for {assignment.subject.name} 
        is due tomorrow ({assignment.due_date.strftime('%B %d, %Y at %I:%M %p')}).
        
        Please make sure to submit your work on time.
        
        Assignment Details:
        - Subject: {assignment.subject.name}
        - Due: {assignment.due_date.strftime('%B %d, %Y at %I:%M %p')}
        - Maximum Score: {assignment.max_score}
        
        You can view and submit the assignment here:
        {reverse('assignment_detail', kwargs={'pk': assignment.pk})}
        
        Best regards,
        School Management System
        """
        
        if student.user.email:
            send_mail(
                subject,
                message,
                'noreply@school.com',
                [student.user.email],
                fail_silently=True,
            )