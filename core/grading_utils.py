from decimal import Decimal
from django.db.models import Avg, Count, Q
from .models import Grade, Student

def calculate_class_performance(subject, class_level, academic_year, term):
    """
    Calculate comprehensive class performance statistics using Ghanaian standards
    """
    grades = Grade.objects.filter(
        subject=subject,
        student__class_level=class_level,
        academic_year=academic_year,
        term=term
    ).exclude(total_score__isnull=True)
    
    if not grades.exists():
        return None
    
    scores = [float(grade.total_score) for grade in grades]
    total_students = len(scores)
    
    # Calculate basic statistics
    average_score = round(sum(scores) / total_students, 2)
    highest_score = max(scores)
    lowest_score = min(scores)
    
    # Calculate grade distribution (GES system)
    grade_distribution = {
        '1': len([s for s in scores if s >= 90]),
        '2': len([s for s in scores if 80 <= s < 90]),
        '3': len([s for s in scores if 70 <= s < 80]),
        '4': len([s for s in scores if 60 <= s < 70]),
        '5': len([s for s in scores if 50 <= s < 60]),
        '6': len([s for s in scores if 40 <= s < 50]),
        '7': len([s for s in scores if 30 <= s < 40]),
        '8': len([s for s in scores if 20 <= s < 30]),
        '9': len([s for s in scores if s < 20]),
    }
    
    # Calculate passing rate (40% and above is passing in GES system)
    passing_count = len([s for s in scores if s >= 40])
    passing_rate = round((passing_count / total_students) * 100, 1)
    
    return {
        'total_students': total_students,
        'average_score': average_score,
        'highest_score': highest_score,
        'lowest_score': lowest_score,
        'grade_distribution': grade_distribution,
        'passing_rate': passing_rate,
        'excellence_rate': round((grade_distribution['1'] / total_students) * 100, 1),
        'failure_rate': round((grade_distribution['9'] / total_students) * 100, 1)
    }

def get_student_academic_progress(student, academic_year=None):
    """
    Get comprehensive academic progress for a student
    """
    if not academic_year:
        current_year = timezone.now().year
        academic_year = f"{current_year}/{current_year + 1}"
    
    grades = Grade.objects.filter(
        student=student,
        academic_year=academic_year
    ).select_related('subject').order_by('term', 'subject__name')
    
    progress_data = {}
    
    for grade in grades:
        subject_name = grade.subject.name
        if subject_name not in progress_data:
            progress_data[subject_name] = []
        
        progress_data[subject_name].append({
            'term': grade.term,
            'score': float(grade.total_score),
            'ges_grade': grade.ges_grade,
            'grade_description': grade.get_ges_grade_display(),
            'is_passing': grade.is_passing(),
            'performance_level': grade.get_performance_level()
        })
    
    # Calculate overall statistics
    all_scores = [float(grade.total_score) for grade in grades if grade.total_score]
    overall_stats = {
        'average_score': round(sum(all_scores) / len(all_scores), 2) if all_scores else 0,
        'subjects_count': len(progress_data),
        'grades_count': len(grades),
        'passing_subjects': len([g for g in grades if g.is_passing()]),
        'excellent_subjects': len([g for g in grades if g.ges_grade in ['1', '2']])
    }
    
    return {
        'progress_data': progress_data,
        'overall_stats': overall_stats,
        'academic_year': academic_year
    }

def generate_term_report(class_level, academic_year, term):
    """
    Generate comprehensive term report for a class
    """
    grades = Grade.objects.filter(
        student__class_level=class_level,
        academic_year=academic_year,
        term=term
    ).select_related('student', 'subject')
    
    if not grades.exists():
        return None
    
    # Group by subject
    subject_reports = {}
    for grade in grades:
        subject_name = grade.subject.name
        if subject_name not in subject_reports:
            subject_reports[subject_name] = {
                'grades': [],
                'statistics': None
            }
        subject_reports[subject_name]['grades'].append(grade)
    
    # Calculate statistics for each subject
    for subject_name, report_data in subject_reports.items():
        scores = [float(g.total_score) for g in report_data['grades'] if g.total_score]
        if scores:
            report_data['statistics'] = {
                'average': round(sum(scores) / len(scores), 2),
                'highest': max(scores),
                'lowest': min(scores),
                'passing_rate': round(len([s for s in scores if s >= 40]) / len(scores) * 100, 1)
            }
    
    # Calculate class overall statistics
    all_scores = [float(g.total_score) for g in grades if g.total_score]
    class_stats = {
        'total_students': len(set(g.student_id for g in grades)),
        'average_score': round(sum(all_scores) / len(all_scores), 2) if all_scores else 0,
        'passing_rate': round(len([s for s in all_scores if s >= 40]) / len(all_scores) * 100, 1) if all_scores else 0
    }
    
    return {
        'class_level': class_level,
        'academic_year': academic_year,
        'term': term,
        'subject_reports': subject_reports,
        'class_statistics': class_stats,
        'generated_at': timezone.now()
    }