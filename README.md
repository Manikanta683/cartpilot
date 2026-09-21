# CartPilot — Agentic Commerce Assistant

An AI shopping agent that sells end-to-end on Razorpay's test-mode APIs:
recommends products, upsells, creates payment orders/links, and recovers failed
or abandoned checkouts. Every money action is explainable, bounded and gated,
with a full audit trail.

Built for the **Razorpay AI Builders** program
(Track 01: AI Growth & Agentic Commerce).

## Quickstart (zero setup — no keys needed)

The default stack — deterministic stub brain + in-memory mock payments — runs
the whole sell → gate → recover loop out of the box:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed.py      # seed the demo catalog
uvicorn app.main:app --reload
# or run the scripted end-to-end demo: python scripts/demo.py
```

- Chat widget (demo store): http://localhost:8000/widget/
- Merchant dashboard (audit trail): http://localhost:8000/dashboard/
- Health check: http://localhost:8000/health

## Brains & backends

| | Stub (default) | Real |
|---|---|---|
| **Brain** (`CARTPILOT_BRAIN`) | `stub` — deterministic demo agent | `claude` — real Claude agent via **claude-agent-sdk**, in-process MCP tools. Needs `ANTHROPIC_API_KEY` + Claude Code CLI (`npm i -g @anthropic-ai/claude-code`) |
| **Payments** (`CARTPILOT_BACKEND`) | `mock` — in-memory, Razorpay-shaped responses | `razorpay` — real test-mode REST calls. Needs `rzp_test_` keys in `.env` |

Mix freely: `stub`+`mock` for zero-setup demos, `claude`+`mock` to try the real
agent without touching money, `stub`+`razorpay` or `claude`+`razorpay` for the
full real thing. Mock payment URLs are clearly fake (`rzp.io/mock/…`) — nobody
can mistake them for real charges.

Money-gating is enforced **inside the tool implementations**
(`policy.evaluate` + audit log) — never left to the model or the SDK.

## Layout

```
app/            FastAPI backend: chat API, policy gate, webhooks, agent,
                backends (mock Razorpay + real test-mode REST)
widget/         embeddable customer chat widget (demo store page)
dashboard/      merchant audit-trail + recovery dashboard
scripts/        seed catalog, zero-setup demo, M1 acceptance test
tests/          policy-gate, backend, recovery + agent-tool unit tests
policy.yaml     money-action gating rules
ARCHITECTURE.md component map and key flows
BUILD_PLAN.md   full build plan, milestones, video script
```

## The money-action policy

See `policy.yaml`. In short:

- Orders under ₹500 → agent may proceed, with a visible "action taken" banner.
- Orders ₹500–₹5000 → require explicit "yes, pay" confirmation in chat.
- Above ₹5000 → denied, escalate to a human.
- Max 2 recovery nudges per order, then stop.
- Every tool call is logged to the audit trail with the model's stated reason.

## What broke (dev log)

_Keep a running log here — Razorpay explicitly scores an honest account of
what broke and how you fixed it._

- **The confirm loop (M2).** The "yes, pay" confirmation re-ran the policy gate,
  which said "confirm" again — so the agent asked for confirmation forever.
  A unit test (`test_mid_buy_asks_confirmation_then_completes`) caught it.
  Fix: thread a `confirmed=True` flag through the second gate evaluation, so a
  customer's explicit "yes" is honored instead of re-gated.
- **Duplicate policy defaults (M4).** `DEFAULT_POLICY` ended up defined in both
  `policy.py` and `agent.py` after a refactor. Caught on re-read before it could
  drift. Fix: single source of truth in `policy.py`, imported everywhere else.
- (add entries as you build)

## Publishing to GitHub

```bash
# create an empty public repo on github.com first, then:
git remote add origin git@github.com:<your-username>/cartpilot.git
git branch -M main
git push -u origin main
```

Never commit `.env` — it's gitignored. The demo runs on test-mode keys only.

## Submission

- [ ] Public repo, README lets a stranger run the demo in <10 min
- [ ] 5-minute pitch video (script in BUILD_PLAN.md)
- [ ] Architecture doc in repo
- [ ] "What broke" section filled in above
- [ ] AI Builders form submitted with repo + video links
