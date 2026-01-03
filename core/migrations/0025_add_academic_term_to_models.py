# core/migrations/0025_add_academic_term_to_models.py
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_add_academic_period_fields'),
    ]

    operations = [
        # Add academic_term fields to Fee, Grade, and ReportCard models
        migrations.AddField(
            model_name='fee',
            name='academic_term',
            field=models.ForeignKey(
                blank=True,
                help_text='Link to academic period (optional)',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='core.AcademicTerm',
                verbose_name='Academic Period'
            ),
        ),
        migrations.AddField(
            model_name='grade',
            name='academic_term',
            field=models.ForeignKey(
                blank=True,
                help_text='Link to academic period (optional)',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='core.AcademicTerm',
                verbose_name='Academic Period'
            ),
        ),
        migrations.AddField(
            model_name='reportcard',
            name='academic_term',
            field=models.ForeignKey(
                blank=True,
                help_text='Link to academic period (optional)',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='core.AcademicTerm',
                verbose_name='Academic Period'
            ),
        ),
    ]