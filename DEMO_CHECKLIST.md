# CartPilot — 5-minute pitch video checklist

Target artefacts for the video: public repo, working demo, architecture, one
graceful failure, and an honest "what broke".

## Setup (before recording)

```bash
cd ~/workspace/cartpilot && source .venv/bin/activate
rm -f cartpilot.db && python scripts/seed.py   # fresh DB, demo catalog
uvicorn app.main:app                            # no --reload, cleaner logs
```

Open side by side: `http://localhost:8000/widget/` and
`http://localhost:8000/dashboard/`. Start screen recording.

## Beats

- **0:00–0:45 — the problem.** Merchants lose revenue twice: at checkout
  (friction, no guidance) and after it (failed payments nobody follows up).
  CartPilot is an agent that sells and recovers, with every money action gated.
- **0:45–2:15 — the sale (widget).** Type "gift under 2000" → recommendations
  + one upsell. Then "buy gift wrap" → auto-approved banner (under ₹500).
  Then "buy bluetooth speaker" → confirm gate → type "yes, pay" → order created.
- **2:15–3:00 — the gate (dashboard).** Show the audit rows: each action with its
  reason. Say the line: "every money action is explainable, bounded and gated."
- **3:00–4:00 — the failure (terminal + dashboard).** Run three times:
  ```bash
  curl -s -X POST localhost:8000/api/recoveries/trigger \
    -H 'Content-Type: application/json' \
    -d '{"order_ref":"demo-1","session_id":"demo"}'
  ```
  First two → nudge sent. Third → **stop**: case `exhausted`, no third nudge.
  "The agent knows when to quit — that's the guardrail."
- **4:00–4:45 — architecture + what broke.** Flash ARCHITECTURE.md (30s).
  Then the two honest stories from the README: the confirm-loop bug and the
  duplicate-policy cleanup — what broke, how the tests caught it, the fix.
- **4:45–5:00 — close.** "An agent that grows revenue on Razorpay's own rails,
  with guardrails a business can trust. Built in the open — repo linked below."

## After recording

- Upload to YouTube (unlisted) or Loom.
- Put the link at the top of the README.
- Submit the AI Builders form with repo + video links.
