# core/management/commands/backfill_analytics.py
from django.core.management.base import BaseCommand
from core.models import Assignment, AssignmentAnalytics, StudentAssignment
from django.db import transaction
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Backfill analytics for existing assignments and student assignments'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--assignment-ids',
            nargs='+',
            type=int,
            help='Specific assignment IDs to process (space-separated)',
        )
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Force recalculation of existing analytics',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip assignments that already have analytics',
        )
    
    def handle(self, *args, **options):
        assignment_ids = options.get('assignment_ids')
        recalculate = options.get('recalculate')
        skip_existing = options.get('skip_existing')
        
        # Get assignments to process
        if assignment_ids:
            assignments = Assignment.objects.filter(id__in=assignment_ids)
        else:
            assignments = Assignment.objects.all()
        
        total_assignments = assignments.count()
        processed_count = 0
        success_count = 0
        error_count = 0
        
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Starting analytics backfill for {total_assignments} assignments..."
            )
        )
        
        for assignment in assignments:
            processed_count += 1
            try:
                with transaction.atomic():
                    # Check if analytics already exists
                    analytics_exists = hasattr(assignment, 'analytics')
                    
                    if skip_existing and analytics_exists and not recalculate:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping assignment {processed_count}/{total_assignments}: "
                                f"'{assignment.title}' (analytics already exists)"
                            )
                        )
                        continue
                    
                    # Create or get analytics
                    if analytics_exists and recalculate:
                        analytics = assignment.analytics
                        action = "Recalculated"
                    else:
                        analytics, created = AssignmentAnalytics.objects.get_or_create(
                            assignment=assignment
                        )
                        action = "Created" if created else "Updated"
                    
                    # Calculate analytics
                    if analytics.calculate_analytics():
                        success_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"{action} analytics for assignment {processed_count}/{total_assignments}: "
                                f"'{assignment.title}' - "
                                f"{analytics.submission_rate}% submitted, "
                                f"{analytics.graded_students}/{analytics.total_students} graded"
                            )
                        )
                    else:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"Failed to calculate analytics for assignment {processed_count}/{total_assignments}: "
                                f"'{assignment.title}'"
                            )
                        )
                        
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing assignment {processed_count}/{total_assignments}: "
                        f"'{assignment.title}' - {str(e)}"
                    )
                )
                logger.error(f"Backfill error for assignment {assignment.id}: {str(e)}")
        
        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(
            self.style.MIGRATE_HEADING("BACKFILL SUMMARY")
        )
        self.stdout.write(
            self.style.SUCCESS(f"✓ Successful: {success_count}")
        )
        self.stdout.write(
            self.style.WARNING(f"○ Skipped: {processed_count - success_count - error_count}")
        )
        self.stdout.write(
            self.style.ERROR(f"✗ Errors: {error_count}")
        )
        self.stdout.write(
            self.style.MIGRATE_HEADING(f"Total processed: {processed_count}/{total_assignments}")
        )
        
        if error_count == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ Analytics backfill completed successfully!")
            )
        else:
            self.stdout.write(
                self.style.WARNING("⚠️  Analytics backfill completed with some errors.")
            )