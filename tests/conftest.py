import os

# Force REDIS_URL to empty to ensure unit tests run in-memory mode,
# avoiding network calls and latency overhead during test runs.
os.environ["REDIS_URL"] = ""
