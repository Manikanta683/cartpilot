"""Razorpay MCP server connection.

Razorpay publishes an MCP server (first Indian payment gateway to do so):

  Remote: https://mcp.razorpay.com/mcp   (HTTP Basic auth: key_id as username,
                                           key_secret as password)
  Local:  docker run razorpay/mcp
  Repo:   github.com/razorpay/razorpay-mcp-server

Tools we care about: create_order, fetch_order, fetch_order_payments,
create_payment_link, fetch_payment_link, create_refund.

M1 acceptance: scripts/create_test_link.py hits the REST API directly to prove
the test keys work. M3 wires the agent to these MCP tools via claude-agent-sdk
(verified on PyPI, 0.2.157).
"""
import base64
import os

MCP_URL = os.getenv("RAZORPAY_MCP_URL", "https://mcp.razorpay.com/mcp")

TOOLS = [
    "create_order",
    "fetch_order",
    "fetch_order_payments",
    "create_payment_link",
    "fetch_payment_link",
    "create_refund",
]


def auth_headers(key_id, key_secret):
    token = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def check_env():
    """M1: fail fast with a clear message if test keys are missing."""
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret or "xxxx" in key_id:
        raise SystemExit(
            "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not set.\n"
            "Sign up at dashboard.razorpay.com, switch to TEST mode,\n"
            "copy the test key pair into your .env file."
        )
    if not key_id.startswith("rzp_test_"):
        raise SystemExit(
            f"Key {key_id!r} is not a TEST key. Use a rzp_test_ key — never live keys."
        )
    return key_id, key_secret
