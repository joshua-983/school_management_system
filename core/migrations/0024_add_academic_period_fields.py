# core/migrations/0024_add_academic_period_fields.py
from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_convert_terms_to_academic_periods'),  # Replace with your actual last migration number
    ]

    operations = [
        # Add new fields to AcademicTerm
        migrations.AddField(
            model_name='academicterm',
            name='period_system',
            field=models.CharField(
                choices=[
                    ('TERM', '3-Term System'),
                    ('SEMESTER', '2-Semester System'),
                    ('QUARTER', '4-Quarter System'),
                    ('TRIMESTER', '3-Trimester System'),
                    ('CUSTOM', 'Custom System')
                ],
                default='TERM',
                help_text='Type of academic period system',
                max_length=10,
                verbose_name='Academic Period System'
            ),
        ),
        migrations.AddField(
            model_name='academicterm',
            name='period_number',
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text='1, 2, 3 for Terms; 1, 2 for Semesters; 1-4 for Quarters',
                verbose_name='Period Number'
            ),
        ),
        migrations.AddField(
            model_name='academicterm',
            name='name',
            field=models.CharField(
                blank=True,
                help_text='Optional custom name (e.g., "First Term", "Fall Semester")',
                max_length=100,
                verbose_name='Period Name'
            ),
        ),
        migrations.AddField(
            model_name='academicterm',
            name='is_locked',
            field=models.BooleanField(
                default=False,
                help_text='Lock period to prevent modifications',
                verbose_name='Lock Period'
            ),
        ),
        migrations.AddField(
            model_name='academicterm',
            name='sequence_num',
            field=models.PositiveSmallIntegerField(
                default=1,
                editable=False,
                verbose_name='Sequence Number'
            ),
        ),
        
        # Add field to SchoolConfiguration
        migrations.AddField(
            model_name='schoolconfiguration',
            name='academic_period_system',
            field=models.CharField(
                choices=[
                    ('TERM', '3-Term System'),
                    ('SEMESTER', '2-Semester System'),
                    ('QUARTER', '4-Quarter System'),
                    ('TRIMESTER', '3-Trimester System'),
                    ('CUSTOM', 'Custom System')
                ],
                default='TERM',
                help_text='System used for academic periods (Terms, Semesters, etc.)',
                max_length=10,
                verbose_name='Academic Period System'
            ),
        ),
        
        # Update unique constraint - CORRECT SYNTAX
        migrations.AlterUniqueTogether(
            name='academicterm',
            unique_together={('period_system', 'period_number', 'academic_year')},
        ),
    ]