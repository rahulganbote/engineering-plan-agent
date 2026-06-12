"""
Integration test to verify Jira connectivity and credentials.
"""
import sys
import os
import base64
import requests
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.config import settings
from src.integrations.jira import _credentials_status, _basic_auth_header

def test_jira_unauthorized_boundary():
    """
    Test endpoint reachability and verify that Jira returns 401 Unauthorized
    when provided with an invalid token.
    """
    print("--- Testing Jira API Reachability with INVALID credentials ---")
    base_url = settings.jira_base_url or "https://your-domain.atlassian.net"
    email = settings.jira_email or "test@example.com"
    token = "INVALID_TOKEN_FOR_TESTING"
    
    url = f"{base_url.rstrip('/')}/rest/api/3/issue"
    auth_str = f"{email}:{token}".encode("utf-8")
    headers = {
        "Authorization": "Basic " + base64.b64encode(auth_str).decode("ascii"),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    payload = {
        "fields": {
            "project": {"key": settings.jira_project_key or "TEST"},
            "summary": "[EM Copilot] Integration Diagnostic test",
            "issuetype": {"name": settings.jira_issue_type or "Task"},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "This is a diagnostic task test."}
                        ]
                    }
                ]
            }
        }
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Jira API Response Code: {r.status_code}")
        # We expect a 401 Unauthorized status because the token is explicitly invalid
        assert r.status_code == 401, f"Expected 401 Unauthorized, got {r.status_code}: {r.text}"
        print("Success: Endpoint is reachable, and returned expected 401 response.")
        return True
    except requests.exceptions.ConnectionError:
        print("[WARNING] Could not connect to Jira server at:", base_url)
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error during connection check: {e}")
        return False

def test_jira_configured_credentials():
    """
    If Jira credentials are configured in the environment, verify they are valid
    by calling a read-only endpoint (myself).
    """
    print("\n--- Testing Configured Jira Credentials ---")
    ok, why_not = _credentials_status()
    if not ok:
        print(f"Jira credentials are not fully configured: {why_not}")
        print("Skipping active credential verification.")
        return

    url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/myself"
    headers = {
        "Authorization": _basic_auth_header(),
        "Accept": "application/json",
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            user_data = r.json()
            display_name = user_data.get("displayName", "Unknown User")
            print(f"Success: Connected to Jira successfully as '{display_name}'!")
        else:
            print(f"[ERROR] Jira auth failed with HTTP {r.status_code}: {r.text}")
            assert False, f"Configured credentials returned HTTP {r.status_code}"
    except Exception as e:
        print(f"[ERROR] Failed to verify configured credentials: {e}")
        raise

if __name__ == "__main__":
    try:
        boundary_ok = test_jira_unauthorized_boundary()
        if boundary_ok:
            test_jira_configured_credentials()
            print("\nAll Jira integration tests ran successfully!")
        else:
            print("\nSkipped or failed connection checks.")
    except AssertionError as e:
        print(f"\nAssertion Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
