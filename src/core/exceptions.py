"""
src/core/exceptions.py
══════════════════════
Custom application exceptions for security and cost governance.
"""


class GovernedFailure(Exception):
    """Base for expected/user-facing pipeline failures (as opposed to bugs)."""

    user_message: str = "An unexpected error occurred."


class QuotaExceededError(GovernedFailure):
    """Raised when API credits/tokens have expired or reached limit."""

    user_message: str = "Your API Credits/Tokens has expired or reached limit. Please try again later. Sorry."


class BudgetBreachedError(GovernedFailure):
    """Raised when the cost threshold for a single run is exceeded."""

    def __init__(self, message: str):
        super().__init__(message)
        self.user_message = f"Pipeline execution aborted: {message}"


class RunCanceledError(GovernedFailure):
    """Raised when the user cancels a run via POST /runs/{run_id}/cancel.

    Cancellation is cooperative: the pipeline observes the cancel flag between
    LangGraph node transitions (inside _set_status) and raises this to unwind.
    Mid-flight LLM calls in specialist agents finish first — cancellation is
    not instant, but stops within one LLM-call worth of time.
    """

    user_message: str = "Run canceled by user."
