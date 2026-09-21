import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db, recovery


def fresh_db(tmp_path):
    p = str(tmp_path / "rec.db")
    db.init_db(p)
    return p


def test_first_failure_opens_case_and_nudges(tmp_path):
    p = fresh_db(tmp_path)
    r = recovery.handle_failure(p, "s1", "order_1")
    assert r["action"] == "nudge_sent" and r["nudge"] == 1
    cases = db.get_recoveries(p)
    assert len(cases) == 1 and cases[0]["status"] == "open"


def test_second_nudge_then_stop(tmp_path):
    p = fresh_db(tmp_path)
    recovery.handle_failure(p, "s1", "order_2")
    r2 = recovery.handle_failure(p, "s1", "order_2")
    assert r2["action"] == "nudge_sent" and r2["nudge"] == 2
    r3 = recovery.handle_failure(p, "s1", "order_2")
    assert r3["action"] == "stop"
    cases = db.get_recoveries(p)
    assert cases[0]["status"] == "exhausted"
    r4 = recovery.handle_failure(p, "s1", "order_2")
    assert r4["action"] == "none"


def test_each_order_gets_own_case(tmp_path):
    p = fresh_db(tmp_path)
    recovery.handle_failure(p, "s1", "order_a")
    recovery.handle_failure(p, "s1", "order_b")
    assert len(db.get_recoveries(p)) == 2
