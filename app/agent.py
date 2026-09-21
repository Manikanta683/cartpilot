"""The selling agent.

Runs in STUB mode until M3 (no API keys needed): keyword matching over the
real catalog so the widget and dashboard are demoable from day one.

M3 wiring (real mode):
  1. pip install the Claude Agent SDK (verify package name first).
  2. Give the agent the MCP tools from app.mcp_client (create_order,
     create_payment_link, ...).
  3. Route every money tool call through app.policy.evaluate first, and
     log the decision + reason via app.db.log_audit.
  4. Keep the SYSTEM_PROMPT's rules — they are the product's guardrails.
"""
import json
import os

from . import config, db as database

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


def _stub_reply(message, db_path):
    products = database.get_products(db_path)
    msg = message.lower()
    hits = [p for p in products if p["name"].lower().split()[0] in msg or p["category"].lower() in msg]
    picks = (hits or products)[:3]
    lines = ["Here's what I'd recommend:"]
    for p in picks:
        lines.append(f"- {p['name']} — ₹{p['price_paise'] / 100:,.0f} ({p['description']})")
    if len(picks) >= 2:
        addon = picks[-1]
        lines.append(f"\nAdd-on idea: {addon['name']} pairs well with this.")
    lines.append("\nWant me to create a payment link for any of these? (stub mode — real checkout lands in M3)")
    return "\n".join(lines)


async def handle_message(session_id, message, db_path):
    if config.STUB_MODE:
        reply = _stub_reply(message, db_path)
        database.log_audit(
            db_path, session_id, "agent(stub)", "chat_reply",
            json.dumps({"message": message}), "stub mode", "ok",
        )
        return reply
    # TODO M3: real agent wiring goes here.
    raise NotImplementedError("Real agent mode not wired yet — see module docstring.")
