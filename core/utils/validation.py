# Create a new file: core/utils/validation.py
import re
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

def validate_grade_data(data):
    """
    Comprehensive grade data validation
    Returns: (is_valid, errors, cleaned_data)
    """
    errors = []
    cleaned_data = {}
    
    # Define max scores
    max_scores = {
        'classwork_score': 30,
        'homework_score': 10,
        'test_score': 10,
        'exam_score': 50
    }
    
    # Validate score ranges
    total_score = Decimal('0.00')
    
    for field, max_score in max_scores.items():
        if field in data:
            try:
                score_str = str(data[field]).strip()
                if not score_str:
                    score = Decimal('0.00')
                else:
                    score = Decimal(score_str)
                
                if score < 0:
                    errors.append(f"{field.replace('_', ' ').title()} cannot be negative")
                elif score > max_score:
                    errors.append(f"{field.replace('_', ' ').title()} cannot exceed {max_score}%")
                else:
                    cleaned_data[field] = score
                    total_score += score
                    
            except (InvalidOperation, ValueError):
                errors.append(f"Invalid {field.replace('_', ' ').title()} format: '{data.get(field)}'")
                cleaned_data[field] = Decimal('0.00')
    
    # Validate total doesn't exceed 100%
    if total_score > 100:
        errors.append(f"Total score cannot exceed 100%. Current total: {total_score}%")
    
    # Validate academic year format
    if 'academic_year' in data:
        academic_year = str(data['academic_year']).strip()
        if not re.match(r'^\d{4}/\d{4}$', academic_year):
            errors.append("Academic year must be in format YYYY/YYYY")
        else:
            # Validate consecutive years
            try:
                year1, year2 = map(int, academic_year.split('/'))
                if year2 != year1 + 1:
                    errors.append("The second year must be exactly one year after the first year")
                else:
                    cleaned_data['academic_year'] = academic_year
            except (ValueError, IndexError):
                errors.append("Invalid academic year format")
    
    # Validate term
    if 'term' in data:
        try:
            term = int(data['term'])
            if term not in [1, 2, 3]:
                errors.append("Term must be 1, 2, or 3")
            else:
                cleaned_data['term'] = term
        except (ValueError, TypeError):
            errors.append("Invalid term format")
    
    # Validate student exists and is active
    if 'student' in data:
        from ..models import Student
        try:
            student = Student.objects.get(pk=data['student'], is_active=True)
            cleaned_data['student'] = student
        except Student.DoesNotExist:
            errors.append("Selected student not found or is inactive")
    
    # Validate subject exists and is active
    if 'subject' in data:
        from ..models import Subject
        try:
            subject = Subject.objects.get(pk=data['subject'], is_active=True)
            cleaned_data['subject'] = subject
        except Subject.DoesNotExist:
            errors.append("Selected subject not found or is inactive")
    
    # Validate no duplicate grade
    if all(key in cleaned_data for key in ['student', 'subject', 'academic_year', 'term']):
        from ..models import Grade
        existing = Grade.objects.filter(
            student=cleaned_data['student'],
            subject=cleaned_data['subject'],
            academic_year=cleaned_data['academic_year'],
            term=cleaned_data['term']
        ).exists()
        
        if existing:
            errors.append(
                f"A grade already exists for {cleaned_data['student'].get_full_name()} "
                f"in {cleaned_data['subject'].name} "
                f"for {cleaned_data['academic_year']} Term {cleaned_data['term']}"
            )
    
    # Add total score to cleaned data
    cleaned_data['total_score'] = total_score
    
    return len(errors) == 0, errors, cleaned_data

def validate_bulk_grade_data(data_list, assignment, term):
    """
    Validate bulk grade data
    """
    errors = []
    valid_data = []
    
    for i, row in enumerate(data_list, start=2):  # Start at 2 for Excel/CSV row numbers
        try:
            row_errors = []
            
            # Validate student_id
            student_id = row.get('student_id', '').strip()
            if not student_id:
                row_errors.append("Missing student ID")
            
            # Validate score
            score_str = row.get('score', '').strip()
            if not score_str:
                row_errors.append("Missing score")
            
            if not row_errors:
                # Validate student exists
                from ..models import Student
                try:
                    student = Student.objects.get(student_id=student_id, is_active=True)
                except Student.DoesNotExist:
                    row_errors.append(f"Student with ID '{student_id}' not found")
                
                # Validate score format and range
                try:
                    score = float(score_str)
                    if score < 0 or score > assignment.max_score:
                        row_errors.append(
                            f"Score {score} is outside valid range (0-{assignment.max_score})"
                        )
                except ValueError:
                    row_errors.append(f"Invalid score format: '{score_str}'")
            
            if row_errors:
                errors.append({
                    'row': i,
                    'student_id': student_id,
                    'errors': row_errors
                })
            else:
                valid_data.append({
                    'row': i,
                    'student': student,
                    'score': score
                })
                
        except Exception as e:
            errors.append({
                'row': i,
                'student_id': row.get('student_id', 'Unknown'),
                'errors': [f"Validation error: {str(e)}"]
            })
    
    return valid_data, errors