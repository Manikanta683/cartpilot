"""Razorpay webhook receiver.

Razorpay signs webhooks with HMAC-SHA256 of the raw body using your webhook
secret, sent as the X-Razorpay-Signature header.

M4 builds the recovery loop on top of payment.failed:
  1. Look up the order/session.
  2. Check policy: nudges_used < max_recovery_nudges.
  3. Send one nudge (and log it to the audit trail).
"""
import hashlib
import hmac
import json

from . import config, db as database, recovery


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def handle(body: bytes, signature: str, db_path: str):
    secret = config.RAZORPAY_WEBHOOK_SECRET
    if secret and not verify_signature(body, signature, secret):
        return {"ok": False, "error": "bad signature"}

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid json"}

    etype = event.get("event", "unknown")
    database.log_audit(
        db_path, "-", "webhook", etype,
        json.dumps({"event": etype}), "webhook received", "ok",
    )

    if etype == "payment.failed":
        entity = event.get("payload", {}).get("payment", {}).get("entity", {})
        order_ref = entity.get("order_id") or entity.get("id") or "unknown"
        result = recovery.handle_failure(db_path, "-", order_ref, reason="payment_failed")
        return {"ok": True, "event": etype, "recovery": result}
    return {"ok": True, "event": etype}
