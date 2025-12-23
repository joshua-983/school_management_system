# core/migrations/xxxx_convert_to_percentage_system.py
from django.db import migrations, models
from decimal import Decimal

def convert_weighted_to_percentage(apps, schema_editor):
    """
    Convert old weighted scores (0-20, 0-30, etc.) to percentages (0-100%)
    This assumes old system used: H=20%, C=30%, T=10%, E=40% weights
    """
    Grade = apps.get_model('core', 'Grade')
    
    print("Starting conversion of grade scores to percentage system...")
    
    # Weights used in OLD system (from your template)
    OLD_HOMEWORK_MAX = Decimal('20.00')  # 20% weight
    OLD_CLASSWORK_MAX = Decimal('30.00')  # 30% weight
    OLD_TEST_MAX = Decimal('10.00')  # 10% weight
    OLD_EXAM_MAX = Decimal('40.00')  # 40% weight
    
    total_grades = Grade.objects.count()
    print(f"Converting {total_grades} grades...")
    
    updated_count = 0
    for grade in Grade.objects.all().iterator(chunk_size=100):
        try:
            # Convert weighted score to percentage
            # Formula: percentage = (weighted_score / max_weight) * 100
            
            if grade.homework_score and OLD_HOMEWORK_MAX > 0:
                grade.homework_percentage = (grade.homework_score / OLD_HOMEWORK_MAX * 100).quantize(Decimal('0.01'))
            
            if grade.classwork_score and OLD_CLASSWORK_MAX > 0:
                grade.classwork_percentage = (grade.classwork_score / OLD_CLASSWORK_MAX * 100).quantize(Decimal('0.01'))
            
            if grade.test_score and OLD_TEST_MAX > 0:
                grade.test_percentage = (grade.test_score / OLD_TEST_MAX * 100).quantize(Decimal('0.01'))
            
            if grade.exam_score and OLD_EXAM_MAX > 0:
                grade.exam_percentage = (grade.exam_score / OLD_EXAM_MAX * 100).quantize(Decimal('0.01'))
            
            # Save will trigger recalculation of total_score
            grade.save()
            updated_count += 1
            
            if updated_count % 100 == 0:
                print(f"Converted {updated_count}/{total_grades} grades...")
                
        except Exception as e:
            print(f"Error converting grade {grade.id}: {e}")
            continue
    
    print(f"Conversion complete! {updated_count} grades converted.")

def reverse_conversion(apps, schema_editor):
    """Reverse conversion - NOT RECOMMENDED but provided for safety"""
    Grade = apps.get_model('core', 'Grade')
    SchoolConfiguration = apps.get_model('core', 'SchoolConfiguration')
    
    print("WARNING: Reversing conversion may lose data accuracy!")
    
    try:
        config = SchoolConfiguration.objects.first()
        if config:
            hw_weight = config.homework_weight
            cw_weight = config.classwork_weight
            t_weight = config.test_weight
            e_weight = config.exam_weight
        else:
            # Default weights
            hw_weight = Decimal('20.00')
            cw_weight = Decimal('30.00')
            t_weight = Decimal('10.00')
            e_weight = Decimal('40.00')
    except:
        hw_weight = Decimal('20.00')
        cw_weight = Decimal('30.00')
        t_weight = Decimal('10.00')
        e_weight = Decimal('40.00')
    
    for grade in Grade.objects.all():
        if grade.homework_percentage:
            grade.homework_score = (grade.homework_percentage / 100 * hw_weight).quantize(Decimal('0.01'))
        if grade.classwork_percentage:
            grade.classwork_score = (grade.classwork_percentage / 100 * cw_weight).quantize(Decimal('0.01'))
        if grade.test_percentage:
            grade.test_score = (grade.test_percentage / 100 * t_weight).quantize(Decimal('0.01'))
        if grade.exam_percentage:
            grade.exam_score = (grade.exam_percentage / 100 * e_weight).quantize(Decimal('0.01'))
        
        grade.save()

class Migration(migrations.Migration):
    dependencies = [
        # Update with your last migration
        ('core', '0013_schoolconfiguration_classwork_weight_and_more'),
    ]

    operations = [
        # Add new percentage fields
        migrations.AddField(
            model_name='grade',
            name='homework_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                max_digits=5,
                verbose_name='Homework Score (%)'
            ),
        ),
        migrations.AddField(
            model_name='grade',
            name='classwork_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                max_digits=5,
                verbose_name='Classwork Score (%)'
            ),
        ),
        migrations.AddField(
            model_name='grade',
            name='test_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                max_digits=5,
                verbose_name='Test Score (%)'
            ),
        ),
        migrations.AddField(
            model_name='grade',
            name='exam_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                max_digits=5,
                verbose_name='Exam Score (%)'
            ),
        ),
        
        # Run data conversion
        migrations.RunPython(convert_weighted_to_percentage, reverse_conversion),
        
        # Remove old fields (AFTER data is converted!)
        migrations.RemoveField(
            model_name='grade',
            name='homework_score',
        ),
        migrations.RemoveField(
            model_name='grade',
            name='classwork_score',
        ),
        migrations.RemoveField(
            model_name='grade',
            name='test_score',
        ),
        migrations.RemoveField(
            model_name='grade',
            name='exam_score',
        ),
    ]