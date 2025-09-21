# core/management/commands/check_backfill_status.py
from django.core.management.base import BaseCommand
from core.models import Assignment, AssignmentAnalytics, StudentAssignment
from django.db.models import Count, Q

class Command(BaseCommand):
    help = 'Check the status of assignment backfills'
    
    def handle(self, *args, **options):
        total_assignments = Assignment.objects.count()
        assignments_with_analytics = Assignment.objects.filter(analytics__isnull=False).count()
        
        # Count student assignments
        student_assignments_stats = StudentAssignment.objects.aggregate(
            total=Count('id'),
            by_status=Count('status')
        )
        
        # Count assignments with missing student assignments
        assignments_missing_students = Assignment.objects.annotate(
            student_count=Count('student_assignments')
        ).filter(student_count=0).count()
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(
            self.style.MIGRATE_HEADING("BACKFILL STATUS REPORT")
        )
        self.stdout.write(f"Total assignments: {total_assignments}")
        self.stdout.write(f"Assignments with analytics: {assignments_with_analytics}")
        self.stdout.write(f"Assignments missing analytics: {total_assignments - assignments_with_analytics}")
        self.stdout.write(f"Total student assignment records: {student_assignments_stats['total']}")
        self.stdout.write(f"Assignments missing student records: {assignments_missing_students}")
        
        if assignments_missing_students > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  {assignments_missing_students} assignments have no student assignments"
                )
            )
        
        if total_assignments - assignments_with_analytics > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  {total_assignments - assignments_with_analytics} assignments missing analytics"
                )
            )
        
        if assignments_missing_students == 0 and total_assignments == assignments_with_analytics:
            self.stdout.write(
                self.style.SUCCESS("✅ All assignments are properly backfilled!")
            )