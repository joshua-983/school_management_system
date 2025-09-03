#!/usr/bin/env python3
"""
Validate that all views follow professional standards.
"""
import glob
import re
from pathlib import Path

def validate_view_file(file_path):
    """Validate a view file meets professional standards."""
    content = Path(file_path).read_text()
    
    checks = {
        'has_django_imports': bool(re.search(r'from django\.', content)),
        'has_proper_class_def': bool(re.search(r'class [A-Z][a-zA-Z]+View\(', content)),
        'no_wildcard_imports': not bool(re.search(r'import \*', content)),
        'has_docstrings': bool(re.search(r'""".*"""', content, re.DOTALL)),
    }
    
    return all(checks.values())

# Validate all view files
for view_file in glob.glob('core/views/*_views.py'):
    is_valid = validate_view_file(view_file)
    status = "✅ PASS" if is_valid else "❌ FAIL"
    print(f"{status}: {view_file}")
