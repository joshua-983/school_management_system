from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models.academic_term import AcademicYear
from core.models import SchoolConfiguration
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync academic years and terms with current date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--years-ahead',
            type=int,
            default=2,
            help='Number of years ahead to create (default: 2)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreate terms even if they exist'
        )

    def handle(self, *args, **options):
        years_ahead = options['years_ahead']
        force = options['force']
        
        self.stdout.write(f"🔍 Starting academic year sync (years ahead: {years_ahead})...")
        
        try:
            # Sync academic years
            created_years = AcademicYear.ensure_years_exist(years_ahead=years_ahead)
            
            if created_years:
                self.stdout.write(self.style.SUCCESS(
                    f"✅ Created {len(created_years)} academic years"
                ))
                for year in created_years:
                    self.stdout.write(f"   - {year.name} ({year.start_date} to {year.end_date})")
            else:
                self.stdout.write(self.style.SUCCESS(
                    "✅ Academic years are already up-to-date"
                ))
            
            # Sync school configuration
            config = SchoolConfiguration.get_config()
            sync_success, sync_message = config.auto_sync_with_academic_system()
            
            if sync_success:
                self.stdout.write(self.style.SUCCESS(
                    f"✅ School configuration synced: {sync_message}"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"⚠️  School configuration sync: {sync_message}"
                ))
            
            # Display current status
            current_year = AcademicYear.get_current_year()
            if current_year:
                self.stdout.write("\n📊 Current Academic Year Status:")
                self.stdout.write(f"   • Academic Year: {current_year.name}")
                self.stdout.write(f"   • Dates: {current_year.start_date} to {current_year.end_date}")
                self.stdout.write(f"   • Total Days: {current_year.get_total_days()} days")
                self.stdout.write(f"   • Progress: {current_year.get_progress_percentage()}%")
                
                terms = current_year.terms.all().order_by('sequence_num')
                if terms.exists():
                    self.stdout.write(f"   • Terms: {terms.count()} terms")
                    total_teaching_days = 0
                    for term in terms:
                        term_days = term.get_total_days()
                        total_teaching_days += term_days
                        self.stdout.write(f"      - {term.name}: {term.start_date} to {term.end_date} ({term_days} days)")
                    
                    self.stdout.write(f"   • Total Teaching Days: {total_teaching_days} days")
                    self.stdout.write(f"   • Vacation Days: {current_year.get_total_days() - total_teaching_days} days")
                else:
                    self.stdout.write(self.style.WARNING(
                        "   • No terms created for current academic year"
                    ))
            
            self.stdout.write(self.style.SUCCESS(
                "\n✅ Academic system sync completed successfully!"
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"❌ Error syncing academic years: {str(e)}"
            ))
            logger.error(f"Academic year sync error: {str(e)}")