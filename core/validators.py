# core/validators.py
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class ComplexityValidator:
    def validate(self, password, user=None):
        if (len(password) < 12 or 
                not any(c.isupper() for c in password) or
                not any(c.islower() for c in password) or
                not any(c.isdigit() for c in password)):
            raise ValidationError(
                _("Password must be at least 12 characters with uppercase, lowercase and numbers."),
                code='password_too_simple',
            )

    def get_help_text(self):
        return _("Your password must be at least 12 characters with uppercase, lowercase and numbers.")