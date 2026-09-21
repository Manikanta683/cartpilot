"""The selling agent.

Two brains (CARTPILOT_BRAIN):
  stub   — deterministic demo brain, no keys needed (default).
  claude — real Claude agent via claude-agent-sdk, with in-process MCP tools.
           Needs ANTHROPIC_API_KEY + the Claude Code CLI.

Two payment backends (CARTPILOT_BACKEND):
  mock     — in-memory, Razorpay-shaped responses (default).
  razorpay — real Razorpay test-mode REST. Needs rzp_test_ keys.

Money-gating is enforced INSIDE the tool implementations (policy.evaluate +
audit log) — never left to the model or the SDK. The SYSTEM_PROMPT rules are
the product's guardrails in both modes.
"""
import json
import re
import uuid

from . import config, db as database
from .policy import DEFAULT_POLICY
from . import policy as policy_mod
from .backend import get_backend

SYSTEM_PROMPT = """You are CartPilot, the shopping assistant for DemoKart, a small
Indian online store. You have tools: search_catalog, check_policy,
create_payment_link, confirm_payment. Rules you must never break:

1. Only recommend products that search_catalog returns. Never invent
   products, prices, or discounts.
2. Recommend at most 3 products per turn. Suggest at most ONE add-on/upsell,
   and only if it is genuinely relevant.
3. Before any money action, call check_policy. If create_payment_link returns
   needs_confirmation, tell the customer the total and ask for an explicit
   "yes, pay" — then call confirm_payment with the token. If it returns denied,
   explain briefly and offer a cheaper alternative or a human.
4. Always state the total in rupees before asking for confirmation.
5. If a payment fails or a link expires, explain what happened in one line,
   then offer exactly one recovery option (retry or a cheaper alternative).
6. Be warm, brief, and concrete. No filler, no emoji spam.
"""

BUY_RE = re.compile(r"\b(buy|checkout|pay|payment link|order it|place order|get it)\b", re.I)
YES_RE = re.compile(r"^\s*(yes|yep|confirm|pay now|do it|ok pay)\b", re.I)
CANCEL_RE = re.compile(r"^\s*(no|cancel|never mind|stop)\b", re.I)
BUDGET_RE = re.compile(r"(?:under|below|less than|within|around)\s*(?:₹|rs\.?\s?|inr\s?)?([\d,]+)", re.I)

_pending = {}         # stub-mode pending: session_id -> {"product": ...}
_claude_pending = {}  # claude-mode pending: token -> {"product": ..., "session_id": ...}


def _get_policy():
    try:
        return policy_mod.load_policy(config.POLICY_PATH)
    except OSError:
        return dict(DEFAULT_POLICY)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

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


def _audit(db_path, session_id, actor, action, args, reason, result):
    database.log_audit(
        db_path, session_id, actor, action,
        json.dumps(args), reason, result,
    )


# ---------------------------------------------------------------------------
# Tool implementations (SDK-independent, unit-testable)
# ---------------------------------------------------------------------------

class ToolContext:
    def __init__(self, db_path, session_id, backend):
        self.db_path = db_path
        self.session_id = session_id
        self.backend = backend


async def tool_search_catalog(ctx, query, max_budget_inr=None):
    products = database.get_products(ctx.db_path)
    hits = _search(products, query or "") or products
    if max_budget_inr:
        hits = [p for p in hits if p["price_paise"] <= float(max_budget_inr) * 100]
    return {"products": [
        {"id": p["id"], "name": p["name"],
         "price_inr": p["price_paise"] / 100, "description": p["description"]}
        for p in hits[:5]
    ]}


async def tool_check_policy(ctx, amount_paise):
    """Read-only policy check. No side effects."""
    pol = _get_policy()
    return policy_mod.evaluate("create_payment_link", int(amount_paise), pol)


async def tool_create_payment_link(ctx, product_id):
    """Policy-gated payment link creation. The gate lives here, in code."""
    pol = _get_policy()
    products = {p["id"]: p for p in database.get_products(ctx.db_path)}
    product = products.get(int(product_id))
    if not product:
        return {"status": "error", "detail": f"unknown product_id {product_id}"}

    amount = product["price_paise"]
    decision = policy_mod.evaluate("create_payment_link", amount, pol)
    args = {"product": product["name"], "amount_paise": amount}

    if decision["decision"] == "deny":
        _audit(ctx.db_path, ctx.session_id, "agent", "create_payment_link",
               args, decision["reason"], "denied")
        return {"status": "denied", "detail": decision["reason"]}

    if decision["decision"] == "confirm":
        token = uuid.uuid4().hex[:12]
        _claude_pending[token] = {"product": product, "session_id": ctx.session_id}
        _audit(ctx.db_path, ctx.session_id, "agent", "policy_check",
               args, decision["reason"], "awaiting confirmation")
        return {"status": "needs_confirmation", "confirmation_token": token,
                "product": product["name"], "amount_inr": amount / 100,
                "detail": decision["reason"]}

    link = ctx.backend.create_payment_link(amount, f"DemoKart: {product['name']}")
    database.record_order(ctx.db_path, ctx.session_id, link["order_id"],
                          amount, "link_created", link["short_url"])
    _audit(ctx.db_path, ctx.session_id, "agent", "create_payment_link",
           args, decision["reason"], "auto-approved")
    return {"status": "created", "product": product["name"],
            "amount_inr": amount / 100, "payment_url": link["short_url"],
            "order_id": link["order_id"]}


async def tool_confirm_payment(ctx, token):
    pending = _claude_pending.pop(token, None)
    if not pending:
        return {"status": "error", "detail": "unknown or expired confirmation token"}
    product = pending["product"]
    amount = product["price_paise"]
    link = ctx.backend.create_payment_link(amount, f"DemoKart: {product['name']}")
    database.record_order(ctx.db_path, ctx.session_id, link["order_id"],
                          amount, "link_created", link["short_url"])
    _audit(ctx.db_path, ctx.session_id, "agent", "create_payment_link",
           {"product": product["name"], "amount_paise": amount},
           "customer confirmed via confirm_payment", "customer confirmed")
    return {"status": "created", "product": product["name"],
            "amount_inr": amount / 100, "payment_url": link["short_url"],
            "order_id": link["order_id"]}


# ---------------------------------------------------------------------------
# Stub brain (default — deterministic, no keys)
# ---------------------------------------------------------------------------

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
    addons = [p for p in products if p not in picks and p["category"] in ("services", "grocery")]
    if addons:
        a = addons[0]
        lines.append(f"\nAdd-on idea: {a['name']} (₹{a['price_paise'] / 100:,.0f}) pairs well with this.")
    lines.append("\nSay 'buy <name>' and I'll set up the payment.")
    return "\n".join(lines)


def _checkout(product, session_id, db_path, pol, backend, confirmed=False):
    amount = product["price_paise"]
    decision = policy_mod.evaluate("create_payment_link", amount, pol)
    args = {"product": product["name"], "amount_paise": amount}

    if decision["decision"] == "confirm" and not confirmed:
        _pending[session_id] = {"product": product}
        _audit(db_path, session_id, "agent(stub)", "policy_check",
               args, decision["reason"], "awaiting confirmation")
        return (f"That's ₹{amount / 100:,.0f} for {product['name']}.\n"
                f"({decision['reason']})\n"
                f"Reply **yes, pay** and I'll create the payment link.")

    if decision["decision"] == "deny":
        _audit(db_path, session_id, "agent(stub)", "policy_check",
               args, decision["reason"], "denied")
        return (f"I can't take that payment myself — {decision['reason']}.\n"
                f"Want me to get a human, or look at something cheaper?")

    how = "auto-approved" if decision["decision"] == "auto" else "customer confirmed"
    link = backend.create_payment_link(amount, f"DemoKart: {product['name']}")
    database.record_order(db_path, session_id, link["order_id"],
                          amount, "link_created", link["short_url"])
    _audit(db_path, session_id, "agent(stub)", "create_payment_link",
           args, decision["reason"], how)
    return (f"✅ Action taken: payment link created for {product['name']} — "
            f"₹{amount / 100:,.0f}.\n({decision['reason']}; {how})\n"
            f"Pay here: {link['short_url']}")


async def _stub_handle(session_id, message, db_path):
    pol = _get_policy()
    backend = get_backend()
    msg = message.strip()

    if session_id in _pending:
        if YES_RE.match(msg):
            product = _pending.pop(session_id)["product"]
            return _checkout(product, session_id, db_path, pol, backend, confirmed=True)
        if CANCEL_RE.match(msg):
            _pending.pop(session_id)
            _audit(db_path, session_id, "agent(stub)", "cancel_pending",
                   {}, "customer cancelled", "ok")
            return "No problem — I've cancelled that. Anything else I can find for you?"
        _pending.pop(session_id)

    if BUY_RE.search(msg):
        products = database.get_products(db_path)
        product = _find_product(products, msg)
        if not product:
            names = ", ".join(p["name"] for p in products[:5])
            return f"Which one? I have: {names}…"
        return _checkout(product, session_id, db_path, pol, backend)

    return _recommend(msg, db_path, session_id)


# ---------------------------------------------------------------------------
# Claude brain (real agent via claude-agent-sdk)
# ---------------------------------------------------------------------------

async def _claude_handle(session_id, message, db_path):
    from claude_agent_sdk import (
        query, ClaudeAgentOptions, create_sdk_mcp_server,
        tool as sdk_tool, AssistantMessage,
    )

    backend = get_backend()
    ctx = ToolContext(db_path, session_id, backend)

    @sdk_tool("search_catalog",
              "Search the DemoKart product catalog. Returns matching products with id, name, price_inr and description. Always use this before recommending anything.",
              {"query": str, "max_budget_inr": float})
    async def _w_search(args):
        return await tool_search_catalog(ctx, args.get("query", ""), args.get("max_budget_inr"))

    @sdk_tool("check_policy",
              "Check the money policy for an amount in paise. Read-only, no side effects. Call before any payment.",
              {"amount_paise": int})
    async def _w_policy(args):
        return await tool_check_policy(ctx, args.get("amount_paise", 0))

    @sdk_tool("create_payment_link",
              "Create a payment link for a catalog product. Policy-gated in code: returns created, needs_confirmation (then ask the customer and call confirm_payment with the token), or denied.",
              {"product_id": int})
    async def _w_create(args):
        return await tool_create_payment_link(ctx, args.get("product_id", 0))

    @sdk_tool("confirm_payment",
              "Complete a payment that is awaiting customer confirmation, using its confirmation token.",
              {"token": str})
    async def _w_confirm(args):
        return await tool_confirm_payment(ctx, args.get("token", ""))

    server = create_sdk_mcp_server("cartpilot",
                                   tools=[_w_search, _w_policy, _w_create, _w_confirm])

    history = database.get_messages(db_path, session_id, limit=8)
    hist_text = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    prompt = (
        f"Recent conversation:\n{hist_text}\n\n"
        f"Customer's new message: {message}\n\n"
        "Respond as CartPilot. Use search_catalog for products, check_policy "
        "before money moves, create_payment_link to charge, and confirm_payment "
        "with the token once the customer confirms."
    )
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"cartpilot": server},
        # Money-gating is enforced inside the tools, not by the SDK.
        permission_mode="bypassPermissions",
    )
    if config.MODEL:
        options.model = config.MODEL

    parts = []
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
    reply = "\n".join(parts).strip()
    _audit(db_path, session_id, "agent(claude)", "chat_reply",
           {"message": message[:200]}, "claude brain", "ok" if reply else "empty")
    return reply or "I couldn't generate a reply — try again."


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

async def handle_message(session_id, message, db_path):
    if config.BRAIN == "claude":
        if not config.ANTHROPIC_API_KEY:
            return ("Claude brain is selected (CARTPILOT_BRAIN=claude) but "
                    "ANTHROPIC_API_KEY is not set. Add it to .env, or switch back "
                    "with CARTPILOT_BRAIN=stub.")
        try:
            return await _claude_handle(session_id, message, db_path)
        except Exception as exc:
            _audit(db_path, session_id, "agent(claude)", "brain_error",
                   {"error": str(exc)[:200]}, "claude brain failed", "error")
            return (f"Claude brain couldn't start ({type(exc).__name__}). It needs "
                    f"the Claude Code CLI (`npm i -g @anthropic-ai/claude-code`) and a "
                    f"valid ANTHROPIC_API_KEY. Set CARTPILOT_BRAIN=stub for the "
                    f"built-in demo brain.")
    return await _stub_handle(session_id, message, db_path)
