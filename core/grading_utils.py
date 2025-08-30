from decimal import Decimal
from .models import Grade

def calculate_class_average(subject, class_level, academic_year, term):
    """
    Calculate class average for a specific subject, class, term and academic year
    """
    grades = Grade.objects.filter(
        subject=subject,
        student__class_level=class_level,
        academic_year=academic_year,
        term=term
    ).exclude(total_score__isnull=True)
    
    if not grades.exists():
        return None
    
    total = sum(float(grade.total_score) for grade in grades)
    return round(total / grades.count(), 2)

def get_grade_distribution(subject, class_level, academic_year, term):
    """
    Get grade distribution for a class in GES format
    """
    grades = Grade.objects.filter(
        subject=subject,
        student__class_level=class_level,
        academic_year=academic_year,
        term=term
    ).exclude(ges_grade='N/A')
    
    distribution = {
        '1': 0, '2': 0, '3': 0, '4': 0, '5': 0,
        '6': 0, '7': 0, '8': 0, '9': 0
    }
    
    for grade in grades:
        distribution[grade.ges_grade] += 1
    
    return distribution

def get_student_progress(student, subject):
    """
    Get a student's progress in a subject across terms
    """
    grades = Grade.objects.filter(
        student=student,
        subject=subject
    ).order_by('academic_year', 'term')
    
    progress = []
    for grade in grades:
        progress.append({
            'academic_year': grade.academic_year,
            'term': grade.term,
            'score': float(grade.total_score),
            'grade': grade.ges_grade,
            'wassce_grade': grade.wassce_grade,
            'is_passing': grade.is_passing
        })
    
    return progress