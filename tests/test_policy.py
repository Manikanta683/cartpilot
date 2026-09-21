import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.policy import evaluate

POLICY = {
    "auto_approve_below_paise": 50000,
    "confirm_below_paise": 500000,
    "allowed_money_actions": ["create_order", "create_payment_link"],
    "max_recovery_nudges": 2,
}


def test_small_order_auto():
    d = evaluate("create_payment_link", 49900, POLICY)
    assert d["decision"] == "auto", d


def test_mid_order_confirm():
    d = evaluate("create_order", 200000, POLICY)
    assert d["decision"] == "confirm", d


def test_large_order_deny():
    d = evaluate("create_order", 600000, POLICY)
    assert d["decision"] == "deny", d


def test_disallowed_action_deny():
    d = evaluate("create_refund", 1000, POLICY)
    assert d["decision"] == "deny", d


def test_nudge_within_bounds():
    d = evaluate("send_recovery_nudge", 0, POLICY, nudges_used=0)
    assert d["decision"] == "auto", d


def test_nudge_limit_stops():
    d = evaluate("send_recovery_nudge", 0, POLICY, nudges_used=2)
    assert d["decision"] == "deny", d
