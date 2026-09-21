"""M1 acceptance test: prove the Razorpay TEST keys work by creating a real
test-mode payment link via the REST API. Run from repo root:

    python scripts/create_test_link.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.mcp_client import check_env

if __name__ == "__main__":
    key_id, key_secret = check_env()
    resp = httpx.post(
        "https://api.razorpay.com/v1/payment_links",
        auth=(key_id, key_secret),
        json={
            "amount": 99900,
            "currency": "INR",
            "description": "CartPilot M1 smoke test",
            "customer": {"name": "Test Buyer", "email": "test@example.com"},
            "notify": {"sms": False, "email": False},
        },
        timeout=20,
    )
    print("status:", resp.status_code)
    data = resp.json()
    if resp.status_code in (200, 201):
        print("M1 PASS — payment link:", data.get("short_url"))
        print("(Test mode: no real money moves. Delete the link from the dashboard.)")
    else:
        print("M1 FAIL —", data)
        sys.exit(1)
