# core/migrations/0027_add_academic_term_indexes.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_migrate_academic_term_data'),
    ]

    operations = [
        # Add indexes for performance
        migrations.AddIndex(
            model_name='academicterm',
            index=models.Index(fields=['period_system', 'academic_year'], name='core_academ_period_sys_year_idx'),
        ),
        migrations.AddIndex(
            model_name='academicterm',
            index=models.Index(fields=['is_active'], name='core_academ_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='academicterm',
            index=models.Index(fields=['start_date', 'end_date'], name='core_academ_start_end_date_idx'),
        ),
        migrations.AddIndex(
            model_name='fee',
            index=models.Index(fields=['academic_term'], name='core_fee_academic_term_idx'),
        ),
        migrations.AddIndex(
            model_name='grade',
            index=models.Index(fields=['academic_term'], name='core_grade_academic_term_idx'),
        ),
        migrations.AddIndex(
            model_name='reportcard',
            index=models.Index(fields=['academic_term'], name='core_report_academic_term_idx'),
        ),
    ]