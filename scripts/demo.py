"""Zero-setup end-to-end demo: sell -> gate -> recover, no API keys needed.

Run from the repo root:  python scripts/demo.py
"""
import asyncio
import os
import sys

os.environ.setdefault("CARTPILOT_DB", "/tmp/cartpilot_demo.db")
os.environ.setdefault("CARTPILOT_BRAIN", "stub")
os.environ.setdefault("CARTPILOT_BACKEND", "mock")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import agent, config, db, recovery  # noqa: E402
from app.backend import reset_backend  # noqa: E402

PRODUCTS = [
    ("Brass Diya Set (12 pc)", 89900, "home", "Handcrafted brass diyas for festive decor"),
    ("Darjeeling First Flush Tea 500g", 74900, "grocery", "Premium single-estate Darjeeling tea"),
    ("Cotton Kurta — Indigo", 129900, "fashion", "Handloom cotton kurta, sizes S–XXL"),
    ("Bluetooth Speaker Mini", 199900, "electronics", "10W speaker, 12-hr battery, IPX5"),
    ("Gift Wrap + Card Service", 14900, "services", "Premium wrapping with a handwritten card"),
    ("Filter Coffee Powder 1kg", 54900, "grocery", "80:20 coffee-chicory blend, Coorg estate"),
    ("Terracotta Planter (Set of 3)", 64900, "home", "Handmade terracotta planters with tray"),
    ("Leather Wallet — Tan", 99900, "fashion", "Full-grain leather bifold wallet"),
]


async def chat(sid, message):
    reply = await agent.handle_message(sid, message, config.DB_PATH)
    print(f"YOU: {message}\nBOT: {reply}\n{'-' * 60}")
    return reply


async def main():
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    db.init_db(config.DB_PATH)
    reset_backend()
    for name, price, cat, desc in PRODUCTS:
        db.add_product(config.DB_PATH, name, price, cat, desc)

    print("=" * 60)
    print("CARTPILOT — full demo (stub brain + mock backend, zero keys)")
    print("=" * 60)

    await chat("demo", "gift under 2000")
    await chat("demo", "buy gift wrap")          # auto-approved (< ₹500)
    await chat("demo", "buy bluetooth speaker")  # confirm gate
    await chat("demo", "yes, pay")               # completes

    print("Simulating a failed payment -> recovery loop:")
    for i in range(1, 4):
        r = recovery.handle_failure(config.DB_PATH, "demo", "order_demo_1")
        print(f"  attempt {i}: {r['action']} — {r.get('detail') or r.get('message', '')[:60]}")

    orders = db.get_orders(config.DB_PATH)
    recs = db.get_recoveries(config.DB_PATH)
    audit = db.get_audit(config.DB_PATH)
    print("-" * 60)
    print(f"DEMO COMPLETE: {len(orders)} orders, "
          f"{len(recs)} recovery case(s) [{recs[0]['status'] if recs else '-'}], "
          f"{len(audit)} audit rows.")
    print("Run the server and open /dashboard to see every step on screen.")


if __name__ == "__main__":
    asyncio.run(main())
