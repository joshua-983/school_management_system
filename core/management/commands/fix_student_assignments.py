from django.core.management.base import BaseCommand
from core.models import Assignment, Student, StudentAssignment

class Command(BaseCommand):
    help = 'Create missing StudentAssignment records for existing assignments'

    def handle(self, *args, **options):
        assignments = Assignment.objects.all()
        for assignment in assignments:
            students = Student.objects.filter(
                class_level=assignment.class_assignment.class_level,
                is_active=True
            )
            
            created_count = 0
            for student in students:
                if not StudentAssignment.objects.filter(
                    student=student, 
                    assignment=assignment
                ).exists():
                    StudentAssignment.objects.create(
                        student=student,
                        assignment=assignment,
                        status='PENDING'
                    )
                    created_count += 1
            
            if created_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created {created_count} StudentAssignment records for assignment: {assignment.title}'
                    )
                )