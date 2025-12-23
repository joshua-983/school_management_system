"""
Permission-specific utilities.
"""
from .main import (
    is_admin, is_teacher, is_student, is_parent,
    is_teacher_or_admin, is_student_or_parent, get_user_role,
    check_report_card_permission, can_edit_grades, can_view_grades
)

__all__ = [
    'is_admin', 'is_teacher', 'is_student', 'is_parent',
    'is_teacher_or_admin', 'is_student_or_parent', 'get_user_role',
    'check_report_card_permission', 'can_edit_grades', 'can_view_grades'
]