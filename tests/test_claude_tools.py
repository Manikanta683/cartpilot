import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import pytest

from app import db
from app.agent import (
    ToolContext,
    tool_search_catalog,
    tool_check_policy,
    tool_create_payment_link,
    tool_confirm_payment,
    _claude_pending,
)
from app.backend import MockBackend, reset_backend


@pytest.fixture
def ctx(tmp_path):
    p = str(tmp_path / "tools.db")
    db.init_db(p)
    db.add_product(p, "Gift Wrap + Card Service", 14900, "services", "wrapping")
    db.add_product(p, "Bluetooth Speaker Mini", 199900, "electronics", "speaker")
    db.add_product(p, "Darjeeling Tea 500g", 74900, "grocery", "tea")
    reset_backend()
    _claude_pending.clear()
    yield ToolContext(p, "s1", MockBackend())
    _claude_pending.clear()
    reset_backend()


def run(coro):
    return asyncio.run(coro)


def test_search_catalog(ctx):
    r = run(tool_search_catalog(ctx, "tea", None))
    assert any(p["name"] == "Darjeeling Tea 500g" for p in r["products"])


def test_search_budget_filter(ctx):
    r = run(tool_search_catalog(ctx, "", 200))
    assert all(p["price_inr"] <= 200 for p in r["products"])
    assert any(p["name"] == "Gift Wrap + Card Service" for p in r["products"])


def test_check_policy_readonly(ctx):
    d = run(tool_check_policy(ctx, 14900))
    assert d["decision"] == "auto"
    d2 = run(tool_check_policy(ctx, 199900))
    assert d2["decision"] == "confirm"


def test_create_auto(ctx):
    r = run(tool_create_payment_link(ctx, 1))
    assert r["status"] == "created"
    assert r["payment_url"].startswith("https://rzp.io/mock/")
    assert len(db.get_orders(ctx.db_path)) == 1


def test_create_confirm_flow(ctx):
    r = run(tool_create_payment_link(ctx, 2))
    assert r["status"] == "needs_confirmation"
    token = r["confirmation_token"]
    r2 = run(tool_confirm_payment(ctx, token))
    assert r2["status"] == "created"
    assert r2["order_id"].startswith("order_mock_")


def test_confirm_bad_token(ctx):
    r = run(tool_confirm_payment(ctx, "nope"))
    assert r["status"] == "error"


def test_create_unknown_product(ctx):
    r = run(tool_create_payment_link(ctx, 999))
    assert r["status"] == "error"
