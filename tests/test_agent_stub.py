import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import pytest

from app import agent, config, db


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "test.db")
    db.init_db(p)
    db.add_product(p, "Gift Wrap + Card Service", 14900, "services", "wrapping")
    db.add_product(p, "Bluetooth Speaker Mini", 199900, "electronics", "speaker")
    db.add_product(p, "Darjeeling Tea 500g", 74900, "grocery", "tea")
    return p


@pytest.fixture(autouse=True)
def clean_pending():
    agent._pending.clear()
    yield
    agent._pending.clear()


def run(session, message, db_path):
    return asyncio.run(agent.handle_message(session, message, db_path))


def test_recommend_searches_catalog(db_path):
    reply = run("s1", "show me tea", db_path)
    assert "Darjeeling" in reply


def test_budget_filter(db_path):
    reply = run("s1", "gift under 200", db_path)
    assert "Gift Wrap" in reply
    assert "Speaker" not in reply


def test_cheap_buy_auto_approves(db_path):
    reply = run("s1", "buy gift wrap", db_path)
    assert "Action taken" in reply
    assert "s1" not in agent._pending
    assert len(db.get_audit(db_path)) >= 1


def test_mid_buy_asks_confirmation_then_completes(db_path):
    reply = run("s2", "buy bluetooth speaker", db_path)
    assert "yes, pay" in reply
    assert "s2" in agent._pending
    reply2 = run("s2", "yes, pay", db_path)
    assert "Action taken" in reply2
    assert "s2" not in agent._pending
    orders = db.get_orders(db_path)
    assert len(orders) == 1 and orders[0]["status"] == "link_created"


def test_cancel_clears_pending(db_path):
    run("s3", "buy bluetooth speaker", db_path)
    assert "s3" in agent._pending
    reply = run("s3", "no, cancel", db_path)
    assert "cancelled" in reply
    assert "s3" not in agent._pending


def test_unknown_product_asks_which(db_path):
    reply = run("s4", "buy a helicopter", db_path)
    assert "Which one" in reply
