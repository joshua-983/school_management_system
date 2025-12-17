"""
MAIN MODELS FILE - HYBRID APPROACH

This file imports from the split modules for backward compatibility.
All models are accessible from here.
"""

# Import everything from the split modules
from .models import *

# Re-export all models for backward compatibility
__all__ = [
    # This file now serves as a bridge to the split models
    # All imports are handled by the models/__init__.py
]
