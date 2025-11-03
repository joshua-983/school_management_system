from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import ClassAssignment, Subject, Teacher, CLASS_LEVEL_CHOICES


class Command(BaseCommand):
    help = 'Fix missing class assignments for all subjects and classes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--academic-year',
            type=str,
            help='Academic year in format YYYY/YYYY (default: current year)',
        )
    
    def handle(self, *args, **options):
        # Set academic year
        if options['academic_year']:
            academic_year = options['academic_year']
        else:
            current_year = timezone.now().year
            academic_year = f"{current_year}/{current_year + 1}"
        
        self.stdout.write(f"Fixing class assignments for academic year: {academic_year}")
        
        # Get all active subjects
        subjects = Subject.objects.filter(is_active=True)
        self.stdout.write(f"Found {subjects.count()} active subjects")
        
        # Get all class levels
        class_levels = [choice[0] for choice in CLASS_LEVEL_CHOICES]
        self.stdout.write(f"Processing {len(class_levels)} class levels")
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        
        for subject in subjects:
            self.stdout.write(f"\nProcessing subject: {subject.name}")
            
            for class_level in class_levels:
                try:
                    # Check if class assignment already exists and is active
                    existing = ClassAssignment.objects.filter(
                        class_level=class_level,
                        subject=subject,
                        academic_year=academic_year,
                        is_active=True
                    ).exists()
                    
                    if existing:
                        skipped_count += 1
                        self.stdout.write(
                            f"  ✓ {class_level}: Already exists"
                        )
                        continue
                    
                    # Find a teacher who can teach this subject
                    teacher = Teacher.objects.filter(
                        subjects=subject,
                        is_active=True
                    ).first()
                    
                    # If no teacher found for this subject, find any active teacher
                    if not teacher:
                        teacher = Teacher.objects.filter(is_active=True).first()
                        if teacher:
                            # Assign the subject to this teacher
                            teacher.subjects.add(subject)
                            self.stdout.write(
                                f"  ⚠ {class_level}: Assigned {teacher.get_full_name()} to teach {subject.name}"
                            )
                    
                    if teacher:
                        # Create the class assignment
                        ClassAssignment.objects.create(
                            class_level=class_level,
                            subject=subject,
                            teacher=teacher,
                            academic_year=academic_year,
                            is_active=True
                        )
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ {class_level}: Created - Teacher: {teacher.get_full_name()}"
                            )
                        )
                    else:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ {class_level}: No active teachers available"
                            )
                        )
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ✗ {class_level}: Error - {str(e)}"
                        )
                    )
        
        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS(
            f"FIX COMPLETED:\n"
            f"• Created: {created_count} new class assignments\n"
            f"• Skipped: {skipped_count} existing assignments\n"
            f"• Errors:  {error_count} assignments failed"
        ))