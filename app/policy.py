"""Money-action gating. Pure logic, no I/O — easy to unit test.

Decisions: "auto" (act + show banner), "confirm" (ask the customer first),
"deny" (refuse and escalate). Every decision carries a human-readable reason,
which is what goes into the audit trail.
"""
import yaml


def load_policy(path="policy.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def evaluate(action, amount_paise, policy, nudges_used=0):
    allowed = policy.get("allowed_money_actions", [])
    if action not in allowed and action != "send_recovery_nudge":
        return {"decision": "deny", "reason": f"action '{action}' is not allowed by policy"}

    if action == "send_recovery_nudge":
        max_n = policy.get("max_recovery_nudges", 2)
        if nudges_used >= max_n:
            return {
                "decision": "deny",
                "reason": f"recovery nudge limit reached ({nudges_used}/{max_n}) — stopping",
            }
        return {
            "decision": "auto",
            "reason": f"recovery nudge {nudges_used + 1}/{max_n} within bounds",
        }

    auto_below = policy.get("auto_approve_below_paise", 0)
    confirm_below = policy.get("confirm_below_paise", 0)
    rupees = amount_paise / 100

    if amount_paise <= auto_below:
        return {
            "decision": "auto",
            "reason": f"₹{rupees:,.0f} is under the ₹{auto_below / 100:,.0f} auto-approve limit",
        }
    if amount_paise <= confirm_below:
        return {
            "decision": "confirm",
            "reason": f"₹{rupees:,.0f} needs explicit customer confirmation (limit ₹{confirm_below / 100:,.0f})",
        }
    return {
        "decision": "deny",
        "reason": f"₹{rupees:,.0f} exceeds the ₹{confirm_below / 100:,.0f} agent limit — escalate to human",
    }
