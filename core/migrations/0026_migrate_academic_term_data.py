# core/migrations/0026_migrate_academic_term_data.py
from django.db import migrations

def migrate_academic_term_data(apps, schema_editor):
    """Migrate existing AcademicTerm data to new system"""
    AcademicTerm = apps.get_model('core', 'AcademicTerm')
    
    for term in AcademicTerm.objects.all():
        # Set period_system based on existing term number
        term.period_system = 'TERM'  # Default to TERM system
        
        # Set period_number from existing term field
        term.period_number = term.term
        
        # Generate name if not set
        if not term.name:
            term.name = f'Term {term.term}'
        
        # Set sequence_num based on term number
        term.sequence_num = term.term
        
        term.save()

def reverse_migration(apps, schema_editor):
    """Reverse the migration if needed"""
    AcademicTerm = apps.get_model('core', 'AcademicTerm')
    
    for term in AcademicTerm.objects.all():
        # Restore term field from period_number
        term.term = term.period_number
        term.save()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_add_academic_term_to_models'),
    ]

    operations = [
        migrations.RunPython(migrate_academic_term_data, reverse_migration),
    ]