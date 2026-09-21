"""The selling agent.

STUB mode (default, no API keys needed): a deterministic demo agent with real
catalog search, budget filtering, upsell logic, and a checkout flow that runs
every money action through the policy gate — so the "explainable, bounded,
gated" bar is demoable from day one. Pending confirmations are kept in memory
(a real deployment would persist them).

M3 wiring (real mode):
  1. `pip install claude-agent-sdk` (verified on PyPI, latest 0.2.157).
  2. Give the agent the MCP tools from app.mcp_client (create_order,
     create_payment_link, ...).
  3. Route every money tool call through app.policy.evaluate first, and
     log the decision + reason via app.db.log_audit.
  4. Keep the SYSTEM_PROMPT's rules — they are the product's guardrails.
"""
import json
import re

from . import config, db as database, policy as policy_mod

SYSTEM_PROMPT = """You are CartPilot, the shopping assistant for DemoKart, a small
Indian online store. Rules you must never break:

1. Only recommend products that the catalog tool returns. Never invent
   products, prices, or discounts.
2. Recommend at most 3 products per turn. Suggest at most ONE add-on/upsell,
   and only if it is genuinely relevant.
3. Before any money action (create order, create payment link), you MUST call
   the policy tool. If it says "confirm", ask the customer for an explicit
   "yes, pay" and do nothing until they confirm. If it says "deny", explain
   briefly and offer to get a human.
4. Always state the total in rupees before asking for confirmation.
5. If a payment fails or a link expires, explain what happened in one line,
   then offer exactly one recovery option (retry or a cheaper alternative).
6. Be warm, brief, and concrete. No filler, no emoji spam.
"""

DEFAULT_POLICY = {
    "auto_approve_below_paise": 50000,
    "confirm_below_paise": 500000,
    "allowed_money_actions": ["create_order", "create_payment_link"],
    "max_recovery_nudges": 2,
}

BUY_RE = re.compile(r"\b(buy|checkout|pay|payment link|order it|place order|get it)\b", re.I)
YES_RE = re.compile(r"^\s*(yes|yep|confirm|pay now|do it|ok pay)\b", re.I)
CANCEL_RE = re.compile(r"^\s*(no|cancel|never mind|stop)\b", re.I)
BUDGET_RE = re.compile(r"(?:under|below|less than|within|around)\s*(?:₹|rs\.?\s?|inr\s?)?([\d,]+)", re.I)

_pending = {}  # session_id -> {"product": dict}


def _get_policy():
    try:
        return policy_mod.load_policy(config.POLICY_PATH)
    except OSError:
        return dict(DEFAULT_POLICY)


def _parse_budget(message):
    m = BUDGET_RE.search(message)
    if m:
        return int(m.group(1).replace(",", "")) * 100
    return None


def _search(products, message):
    words = [w for w in re.findall(r"[a-z]+", message.lower()) if len(w) > 3]
    scored = []
    for p in products:
        hay = f"{p['name']} {p['description']} {p['category']}".lower()
        score = sum(1 for w in words if w in hay)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored]


def _fmt(p):
    return f"- {p['name']} — ₹{p['price_paise'] / 100:,.0f} ({p['description']})"


def _find_product(products, message):
    msg = message.lower()
    for p in products:
        if p["name"].lower() in msg:
            return p
    hits = _search(products, message)
    return hits[0] if hits else None


def _audit(db_path, session_id, action, args, reason, result):
    database.log_audit(
        db_path, session_id, "agent(stub)", action,
        json.dumps(args), reason, result,
    )


def _recommend(message, db_path, session_id):
    products = database.get_products(db_path)
    budget = _parse_budget(message)
    hits = _search(products, message) or products
    if budget:
        hits = [p for p in hits if p["price_paise"] <= budget]
    picks = hits[:3]
    if not picks:
        return "Nothing in the catalog matches that — try 'tea', 'kurta', 'speaker', 'gift' or 'home'."

    lines = ["Here's what I'd recommend:"]
    lines += [_fmt(p) for p in picks]
    # One relevant upsell: cheapest add-on from a different category.
    addons = [p for p in products if p not in picks and p["category"] in ("services", "grocery")]
    if addons:
        a = addons[0]
        lines.append(f"\nAdd-on idea: {a['name']} (₹{a['price_paise'] / 100:,.0f}) pairs well with this.")
    lines.append("\nSay 'buy <name>' and I'll set up the payment.")
    return "\n".join(lines)


def _checkout(product, session_id, db_path, pol, confirmed=False):
    amount = product["price_paise"]
    decision = policy_mod.evaluate("create_payment_link", amount, pol)
    args = {"product": product["name"], "amount_paise": amount}

    if decision["decision"] == "confirm" and not confirmed:
        _pending[session_id] = {"product": product}
        _audit(db_path, session_id, "policy_check", args,
               decision["reason"], "awaiting confirmation")
        return (f"That's ₹{amount / 100:,.0f} for {product['name']}.\n"
                f"({decision['reason']})\n"
                f"Reply **yes, pay** and I'll create the payment link.")

    if decision["decision"] == "deny":
        _audit(db_path, session_id, "policy_check", args, decision["reason"], "denied")
        return (f"I can't take that payment myself — {decision['reason']}.\n"
                f"Want me to get a human, or look at something cheaper?")

    # auto, or confirm + customer already said yes
    how = "auto-approved" if decision["decision"] == "auto" else "customer confirmed"
    database.record_order(db_path, session_id, f"stub_{session_id[:8]}",
                          amount, "link_created", payment_link="(stub)")
    _audit(db_path, session_id, "create_payment_link", args,
           decision["reason"], how)
    return (f"✅ Action taken: payment link created for {product['name']} — "
            f"₹{amount / 100:,.0f}.\n({decision['reason']}; {how})\n"
            f"[stub mode — a real Razorpay link appears here in M3]")


async def handle_message(session_id, message, db_path):
    if not config.STUB_MODE:
        # TODO M3: real agent wiring goes here.
        raise NotImplementedError("Real agent mode not wired yet — see module docstring.")

    pol = _get_policy()
    msg = message.strip()

    if session_id in _pending:
        if YES_RE.match(msg):
            product = _pending.pop(session_id)["product"]
            return _checkout(product, session_id, db_path, pol, confirmed=True)
        if CANCEL_RE.match(msg):
            _pending.pop(session_id)
            _audit(db_path, session_id, "cancel_pending", {}, "customer cancelled", "ok")
            return "No problem — I've cancelled that. Anything else I can find for you?"
        # They named something else; drop the stale pending intent.
        _pending.pop(session_id)

    if BUY_RE.search(msg):
        products = database.get_products(db_path)
        product = _find_product(products, msg)
        if not product:
            names = ", ".join(p["name"] for p in products[:5])
            return f"Which one? I have: {names}…"
        return _checkout(product, session_id, db_path, pol)

    return _recommend(msg, db_path, session_id)
