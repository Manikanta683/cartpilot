"""CartPilot API. Run from the repo root:  uvicorn app.main:app --reload"""
import uuid

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from . import agent, config, db as database, recovery, webhooks

app = FastAPI(title="CartPilot")
database.init_db(config.DB_PATH)


@app.get("/health")
def health():
    return {"ok": True, "stub": config.STUB_MODE}


@app.post("/api/chat")
async def chat(payload: dict):
    session_id = payload.get("session_id") or uuid.uuid4().hex
    message = payload.get("message", "")
    database.save_message(config.DB_PATH, session_id, "user", message)
    reply = await agent.handle_message(session_id, message, config.DB_PATH)
    database.save_message(config.DB_PATH, session_id, "assistant", reply)
    return {"session_id": session_id, "reply": reply}


@app.get("/api/products")
def products():
    return {"products": database.get_products(config.DB_PATH)}


@app.get("/api/audit")
def audit(limit: int = 50):
    return {"audit": database.get_audit(config.DB_PATH, limit)}


@app.get("/api/orders")
def orders():
    return {"orders": database.get_orders(config.DB_PATH)}


@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    return webhooks.handle(body, sig, config.DB_PATH)


@app.post("/api/recoveries/trigger")
def trigger_recovery(payload: dict):
    """Demo helper: simulate a failed payment without a real webhook.
    Body: {"order_ref": "...", "session_id": "...", "reason": "payment_failed"}"""
    return recovery.handle_failure(
        config.DB_PATH,
        payload.get("session_id", "-"),
        payload.get("order_ref", "demo-order"),
        payload.get("reason", "payment_failed"),
    )


@app.get("/api/recoveries")
def recoveries():
    return {"recoveries": database.get_recoveries(config.DB_PATH)}


app.mount("/widget", StaticFiles(directory="widget", html=True), name="widget")
app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")
