# core/management/commands/check_assignment_distribution.py
from django.core.management.base import BaseCommand
from core.models import Assignment, Student, ClassAssignment
from django.db.models import Count

class Command(BaseCommand):
    help = 'Check assignment distribution across classes'

    def handle(self, *args, **options):
        # Check assignments per class
        self.stdout.write("=== ASSIGNMENTS PER CLASS ===")
        class_assignments = ClassAssignment.objects.values(
            'class_level'
        ).annotate(
            assignment_count=Count('assignment')
        ).order_by('class_level')
        
        for ca in class_assignments:
            self.stdout.write(
                f"Class {ca['class_level']}: {ca['assignment_count']} assignments"
            )
        
        # Check students per class with their assignment counts
        self.stdout.write("\n=== STUDENTS AND THEIR ASSIGNMENTS ===")
        students = Student.objects.filter(is_active=True).select_related('user')
        
        for student in students:
            assignment_count = student.studentassignment_set.count()
            self.stdout.write(
                f"{student.get_full_name():<25} | Class: {student.class_level:<4} | "
                f"Assignments: {assignment_count:<2} | Student ID: {student.student_id}"
            )