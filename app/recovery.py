"""Bounded recovery loop (M4).

Triggered by payment.failed webhooks or the manual demo endpoint
(POST /api/recoveries/trigger). For each failed order:

  1. Open one recovery case per order.
  2. Send at most max_recovery_nudges nudges (policy-enforced), then stop.
  3. Log every step to the audit trail.

The stop rule is the point: the agent must know when to quit, not just
when to act.
"""
import json

from . import config, db as database
from .policy import DEFAULT_POLICY
from . import policy as policy_mod


def _get_policy():
    try:
        return policy_mod.load_policy(config.POLICY_PATH)
    except OSError:
        return dict(DEFAULT_POLICY)


def handle_failure(db_path, session_id, order_ref, reason="payment_failed"):
    pol = _get_policy()
    rec = database.get_or_create_recovery(db_path, order_ref, session_id, reason)

    if rec["status"] != "open":
        return {"action": "none", "detail": f"case already {rec['status']}"}

    decision = policy_mod.evaluate(
        "send_recovery_nudge", 0, pol, nudges_used=rec["nudges_sent"]
    )
    args = {"order_ref": order_ref, "nudges_sent": rec["nudges_sent"]}

    if decision["decision"] == "deny":
        database.set_recovery_status(db_path, rec["id"], "exhausted")
        database.log_audit(
            db_path, session_id, "recovery", "stop_recovery",
            json.dumps(args), decision["reason"], "exhausted",
        )
        return {"action": "stop", "detail": decision["reason"]}

    n = database.record_nudge(db_path, rec["id"])
    message = (
        f"Your payment for order {order_ref} didn't go through. "
        f"Want me to send you a fresh payment link? "
        f"(follow-up {n} of {pol['max_recovery_nudges']})"
    )
    database.log_audit(
        db_path, session_id, "recovery", "send_nudge",
        json.dumps(args), decision["reason"], f"nudge {n} sent",
    )
    return {"action": "nudge_sent", "nudge": n, "message": message}
