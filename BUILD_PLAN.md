# CartPilot — Agentic Commerce Assistant
### Build plan for Razorpay AI Builders (Track 01: AI Growth & Agentic Commerce)

## The idea in one line
A conversational agent that sells end-to-end for a demo merchant on Razorpay's
test-mode APIs: it recommends products, upsells and cross-sells, creates payment
orders/links, and recovers failed or abandoned checkouts. Every money action is
explainable, bounded and gated, with a full audit trail.

## Why this wins (the official bar, from razorpay.com/buildathon)
- Track 01 asks for "an agent that grows revenue for a merchant on Razorpay
  test-mode APIs" — conversational checkout, upsell agent, campaign orchestrator.
- The stated bar: every money action explainable, bounded and gated; show the
  audit trail; handle one failure gracefully.
- Submission artefacts: public repo, 5-minute pitch video, architecture, and an
  honest account of what broke during the build.

## Architecture

```
Customer chat widget (embeddable JS)
        |
        v
FastAPI backend ──> Agent (Claude Agent SDK)
        |                 |
        |            Razorpay MCP server (remote, test keys)
        |            tools: create_order, create_payment_link,
        |                   fetch payments, refunds
        v
Webhook receiver ──> recovery loop (failed/abandoned -> nudge -> retry)
        |
        v
Merchant dashboard (audit trail, revenue influenced, recoveries)
        |
SQLite (catalog, sessions, audit log)
```

**Money-action policy (`policy.yaml`)**
- Orders under ₹500: agent may proceed, but shows a visible "action taken" banner.
- Orders above ₹500: require an explicit "yes, pay" confirmation in chat.
- Max 2 recovery nudges per order, then stop. Every tool call is logged with a
  timestamp, arguments, the model's stated reason, and the result.

## Tech stack (assumed — say the word and I'll adapt to JS/TS)
Python 3.11, FastAPI, Anthropic Claude Agent SDK, Razorpay MCP server (remote,
test-mode keys), SQLite, vanilla JS chat widget + dashboard, Render/Railway for
hosting, Loom for the pitch video.

## Milestones — status 2026-09-21

**M1 — Wired up.** ✅ Repo skeleton, FastAPI app, mock backend live; real
test-mode keys still needed for the live acceptance run
(`python scripts/create_test_link.py`).
*Done when:* a script creates a real test-mode payment link end to end.

**M2 — The salesperson.** ✅ Catalog (SQLite), recommendation + one upsell,
working chat widget. 12 tests green.
*Done when:* "birthday gift under ₹2000" returns 3 catalog picks plus an upsell.

**M3 — Money moves.** ✅ Real Claude agent via **claude-agent-sdk** with
in-process MCP tools (`search_catalog`, `check_policy`, `create_payment_link`,
`confirm_payment`); money gate enforced inside the tools. Live run needs
`ANTHROPIC_API_KEY` + Claude Code CLI (+ `rzp_test_` keys for real payments).
*Done when:* full chat → test payment → `order.paid` recorded in the dashboard.

**M4 — The recovery loop.** ✅ Webhook receiver, per-order cases, max 2
policy-capped nudges then stop, dashboard recovery section. 15 tests green.
*Done when:* a failed test payment triggers an agent nudge and the recovery shows
on the dashboard.

**M5 — Harden + ship.** ✅ `scripts/demo.py` (zero-setup full loop),
ARCHITECTURE.md, DEMO_CHECKLIST.md, "what broke" log, publishing guide.
*Done when:* a stranger can clone the repo and run the demo in under 10 minutes.

**M6 — Submit.** ⏳ 5-minute video recorded, repo public, AI Builders form submitted
with repo + video links.

## The 5-minute video script
- 0:00–0:45 — the problem: merchants lose revenue at checkout and in follow-ups.
- 0:45–2:15 — live demo: chat → recommendations → upsell → payment link → test payment.
- 2:15–3:00 — the gate + audit trail (this is the "explainable, bounded" bar, on screen).
- 3:00–4:00 — failure demo: declined payment → agent detects → recovery offer → paid.
- 4:00–4:45 — architecture (30s) + what broke during the build and the fix.
- 4:45–5:00 — close: why agentic commerce is the future, and you built it.

## Submission checklist
- [ ] Public GitHub repo with a clean README (problem, demo video/GIF, architecture, quickstart with test keys)
- [ ] 5-minute pitch video
- [ ] Architecture doc/diagram in the repo
- [ ] "What broke" section in the README — they explicitly ask for this
- [ ] AI Builders form submitted with repo + video links

## Guardrails
- Test-mode keys only. Never real money. Keys in env vars, never committed.
- Cap LLM cost: short context, max turns per session.
- Keep a running dev log of everything that breaks — it becomes the README's
  "what broke" section, which is a scored signal, not an embarrassment.
