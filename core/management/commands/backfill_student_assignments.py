# core/management/commands/backfill_student_assignments.py
from django.core.management.base import BaseCommand
from core.models import Assignment, StudentAssignment, Student
from django.db import transaction
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Create StudentAssignment records for existing assignments and update analytics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--assignment-ids',
            nargs='+',
            type=int,
            help='Specific assignment IDs to process (space-separated)',
        )
        parser.add_argument(
            '--class-levels',
            nargs='+',
            type=str,
            help='Specific class levels to process (space-separated)',
        )
        parser.add_argument(
            '--update-analytics',
            action='store_true',
            help='Update analytics after creating student assignments',
        )
    
    def handle(self, *args, **options):
        assignment_ids = options.get('assignment_ids')
        class_levels = options.get('class_levels')
        update_analytics = options.get('update_analytics')
        
        # Get assignments to process
        assignments = Assignment.objects.all()
        
        if assignment_ids:
            assignments = assignments.filter(id__in=assignment_ids)
        
        if class_levels:
            assignments = assignments.filter(class_assignment__class_level__in=class_levels)
        
        total_assignments = assignments.count()
        total_created = 0
        processed_count = 0
        
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Starting student assignments backfill for {total_assignments} assignments..."
            )
        )
        
        for assignment in assignments:
            processed_count += 1
            try:
                with transaction.atomic():
                    students = Student.objects.filter(
                        class_level=assignment.class_assignment.class_level,
                        is_active=True
                    )
                    
                    created_count = 0
                    for student in students:
                        obj, created = StudentAssignment.objects.get_or_create(
                            student=student,
                            assignment=assignment,
                            defaults={'status': 'PENDING'}
                        )
                        if created:
                            created_count += 1
                    
                    total_created += created_count
                    
                    # Update analytics if requested
                    analytics_updated = False
                    if update_analytics and hasattr(assignment, 'analytics'):
                        analytics_updated = assignment.analytics.calculate_analytics()
                    
                    if created_count > 0:
                        message = (
                            f"Created {created_count} student assignments for "
                            f"'{assignment.title}' ({assignment.class_assignment.class_level})"
                        )
                        if analytics_updated:
                            message += " and updated analytics"
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"[{processed_count}/{total_assignments}] {message}"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"[{processed_count}/{total_assignments}] "
                                f"No new student assignments needed for '{assignment.title}'"
                            )
                        )
                        
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[{processed_count}/{total_assignments}] "
                        f"Error processing assignment '{assignment.title}': {str(e)}"
                    )
                )
                logger.error(f"Student assignments backfill error: {str(e)}")
        
        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(
            self.style.MIGRATE_HEADING("BACKFILL SUMMARY")
        )
        self.stdout.write(
            self.style.SUCCESS(f"✓ Total student assignments created: {total_created}")
        )
        self.stdout.write(
            self.style.SUCCESS(f"✓ Processed assignments: {processed_count}/{total_assignments}")
        )
        
        if total_created > 0:
            self.stdout.write(
                self.style.SUCCESS("✅ Student assignments backfill completed successfully!")
            )
        else:
            self.stdout.write(
                self.style.WARNING("ℹ️  No new student assignments were created.")
            )