"""Runtime configuration. All secrets come from the environment, never from code."""
import os

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DB_PATH = os.getenv("CARTPILOT_DB", "cartpilot.db")
STUB_MODE = os.getenv("CARTPILOT_STUB", "true").lower() == "true"
POLICY_PATH = os.getenv("CARTPILOT_POLICY", "policy.yaml")
