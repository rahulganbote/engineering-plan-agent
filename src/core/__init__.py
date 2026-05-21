"""src/core — shared models, config, and logging for the EM Copilot pipeline."""
from src.core.models import PipelineState  # noqa: F401 — convenience re-export
from src.core.config import settings       # noqa: F401
from src.core.logger import get_logger     # noqa: F401
