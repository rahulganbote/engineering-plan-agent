import os
import sys
from pathlib import Path

# Add project root to path so we can import src modules if needed
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import redis
except ImportError:
    print("Error: The 'redis' library is not installed in this environment.")
    print("Please install it by running: .venv/bin/pip install redis")
    sys.exit(1)

def main():
    # Load environment variables from secrets/.env
    env_path = Path(__file__).resolve().parents[1] / "secrets" / ".env"
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip('"').strip("'")

    redis_url = env_vars.get("REDIS_URL") or os.environ.get("REDIS_URL")
    if not redis_url:
        print("Error: REDIS_URL not found in secrets/.env or environment.")
        sys.exit(1)

    print(f"Connecting to Redis...")
    try:
        r = redis.from_url(redis_url)
        keys = r.keys("em-copilot:*")
        print(f"Successfully connected! Found {len(keys)} cached keys matching 'em-copilot:*':")
        for k in sorted(keys):
            print(f" - {k.decode('utf-8')}")
    except Exception as e:
        print(f"Error: Failed to connect to Redis: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
