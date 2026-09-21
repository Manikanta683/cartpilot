# CartPilot — Architecture

## Components

```
widget/            Embeddable customer chat (vanilla JS) + demo store page
dashboard/         Merchant view: audit trail + recovery cases (auto-refresh)
app/main.py        FastAPI: /api/chat, /api/products, /api/audit, /api/orders,
                   /api/recoveries/*, /webhooks/razorpay; serves widget + dashboard
app/agent.py       Selling agent — stub brain (default) or Claude brain via
                   claude-agent-sdk with in-process MCP tools
app/backend.py     Payment backends: MockBackend (in-memory) or RazorpayBackend
                   (real test-mode REST), chosen by CARTPILOT_BACKEND
app/policy.py      Pure money-gating logic: auto / confirm / deny (+ reasons)
app/recovery.py    Bounded recovery loop: per-order cases, capped nudges, stop rule
app/webhooks.py    Razorpay webhook signature verification + event routing
app/mcp_client.py  Razorpay MCP server connection details (remote, test-mode keys)
app/db.py          SQLite: products, sessions, messages, audit_log, orders, recoveries
policy.yaml        Gating rules: auto < ₹500, confirm ≤ ₹5000, deny above,
                   max 2 recovery nudges per order
```

## Brains and backends

The agent is two independent choices:

- **Brain** (`CARTPILOT_BRAIN`): `stub` is a deterministic demo agent —
  catalog search, one upsell, policy-gated checkout. `claude` runs a real
  Claude agent through the **claude-agent-sdk** (`query` + `create_sdk_mcp_server`),
  with four in-process MCP tools: `search_catalog`, `check_policy`,
  `create_payment_link`, `confirm_payment`.
- **Backend** (`CARTPILOT_BACKEND`): `mock` is in-memory and returns
  Razorpay-shaped responses; `razorpay` makes real test-mode REST calls.

The critical design point: the money gate (`policy.evaluate` + `db.log_audit`)
lives **inside the tool implementations** (`tool_create_payment_link`, …),
so it holds for both brains. The model decides what to sell; the code decides
what money may move.

## Flow 1 — Chat to checkout

Widget → `POST /api/chat` → agent searches the catalog (keyword match + budget
filter), suggests at most one upsell. On a buy intent:

1. `policy.evaluate("create_payment_link", amount, policy)` runs.
2. **auto** → order recorded, audit-logged with reason, banner shown.
3. **confirm** → pending intent stored, customer must reply "yes, pay";
   on confirmation the gate is re-checked with `confirmed=True` and the order completes.
4. **deny** → refused with the reason, human escalation offered.

Every money action lands in `audit_log` with the model's/policy's stated reason.
That table is the "explainable, bounded, gated" bar, rendered live on the dashboard.

## Flow 2 — Payment failure to recovery

`payment.failed` webhook → HMAC-SHA256 signature verified → `recovery.handle_failure`
opens (or reuses) one case per order → policy check on nudge count → nudge sent
(audit-logged) or stop at the limit (case marked `exhausted`, audit-logged).
`POST /api/recoveries/trigger` simulates this for demos without a real webhook.

## Flow 3 — Merchant oversight

Dashboard polls `/api/audit` and `/api/recoveries` every 3s. Nothing the agent
does is invisible: every tool call, gate decision, nudge, and stop is on screen.

## Why these choices

- **FastAPI + SQLite**: zero-infra demo; a reviewer can run it in under 10 minutes.
- **Stub-first agent**: the full UX (sell → gate → recover) is demoable before any
  API keys exist. The real agent swaps into `handle_message` without touching the API.
- **Claude Agent SDK (M3, done)**: mirrors Razorpay's own Agent Studio, which is
  built on the Claude Agent SDK — the stack speaks their language. The real
  agent runs through `query()` with an in-process MCP server; the money gate
  stays in the tool code where tests can reach it.
- **Test-mode keys only**; secrets live in env vars, never in code or git.

## M3 today

`CARTPILOT_BRAIN=claude` runs the real agent: `query()` with `SYSTEM_PROMPT`,
an in-process MCP server (`create_sdk_mcp_server`) exposing the four tools,
and `permission_mode="bypassPermissions"` — safe because the money gate is
enforced inside the tools. Needs `ANTHROPIC_API_KEY` + the Claude Code CLI.
To go fully live: add `rzp_test_` keys and set `CARTPILOT_BACKEND=razorpay`.
