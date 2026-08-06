import os

import pytest

from src.api.limiter import limiter

# Force REDIS_URL to empty to ensure unit tests run in-memory mode,
# avoiding network calls and latency overhead during test runs.
os.environ["REDIS_URL"] = ""

# Disable SlowAPI rate limiting globally during test execution to prevent 429s on unit tests
limiter.enabled = False


@pytest.fixture(autouse=True, scope="function")
def disable_limiter_fixture():
    limiter.enabled = False
