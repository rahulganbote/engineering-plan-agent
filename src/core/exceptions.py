"""
src/core/exceptions.py
══════════════════════
Custom application exceptions for security and cost governance.
"""

class BudgetBreachedError(Exception):
    """Raised when the cost threshold for a single run is exceeded."""
    pass
