"""SQLite storage: catalog, sessions, messages, audit log, orders."""
import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price_paise INTEGER NOT NULL,
    category TEXT,
    description TEXT
);
CREATE TABLE IF NOT EXISTS sessions(
    id TEXT PRIMARY KEY,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    role TEXT,
    content TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    session_id TEXT,
    actor TEXT,
    action TEXT,
    args_json TEXT,
    reason TEXT,
    result TEXT
);
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rzp_order_id TEXT,
    session_id TEXT,
    amount_paise INTEGER,
    currency TEXT DEFAULT 'INR',
    status TEXT,
    payment_link TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS recoveries(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_ref TEXT UNIQUE,
    session_id TEXT,
    reason TEXT,
    nudges_sent INTEGER DEFAULT 0,
    status TEXT DEFAULT 'open',
    created_at TEXT,
    updated_at TEXT
);
"""


def _conn(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def init_db(path):
    con = _conn(path)
    con.executescript(SCHEMA)
    con.commit()
    con.close()


def log_audit(path, session_id, actor, action, args_json="{}", reason="", result=""):
    con = _conn(path)
    con.execute(
        "INSERT INTO audit_log(created_at, session_id, actor, action, args_json, reason, result)"
        " VALUES (?,?,?,?,?,?,?)",
        (now(), session_id, actor, action, args_json, reason, result),
    )
    con.commit()
    con.close()


def get_audit(path, limit=50):
    con = _conn(path)
    rows = con.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def save_message(path, session_id, role, content):
    con = _conn(path)
    con.execute(
        "INSERT OR IGNORE INTO sessions(id, created_at) VALUES (?,?)", (session_id, now())
    )
    con.execute(
        "INSERT INTO messages(session_id, role, content, created_at) VALUES (?,?,?,?)",
        (session_id, role, content, now()),
    )
    con.commit()
    con.close()


def get_products(path):
    con = _conn(path)
    rows = con.execute("SELECT * FROM products ORDER BY id").fetchall()
    con.close()
    return [dict(r) for r in rows]


def add_product(path, name, price_paise, category="", description=""):
    con = _conn(path)
    con.execute(
        "INSERT INTO products(name, price_paise, category, description) VALUES (?,?,?,?)",
        (name, price_paise, category, description),
    )
    con.commit()
    con.close()


def record_order(path, session_id, rzp_order_id, amount_paise, status, payment_link=""):
    con = _conn(path)
    con.execute(
        "INSERT INTO orders(rzp_order_id, session_id, amount_paise, status, payment_link, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (rzp_order_id, session_id, amount_paise, status, payment_link, now()),
    )
    con.commit()
    con.close()


def get_orders(path):
    con = _conn(path)
    rows = con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_or_create_recovery(path, order_ref, session_id, reason):
    con = _conn(path)
    row = con.execute("SELECT * FROM recoveries WHERE order_ref=?", (order_ref,)).fetchone()
    if row:
        con.close()
        return dict(row)
    cur = con.execute(
        "INSERT INTO recoveries(order_ref, session_id, reason, nudges_sent, status, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (order_ref, session_id, reason, 0, "open", now(), now()),
    )
    rid = cur.lastrowid
    con.commit()
    row = con.execute("SELECT * FROM recoveries WHERE id=?", (rid,)).fetchone()
    con.close()
    return dict(row)


def record_nudge(path, rid):
    con = _conn(path)
    con.execute(
        "UPDATE recoveries SET nudges_sent=nudges_sent+1, updated_at=? WHERE id=?",
        (now(), rid),
    )
    n = con.execute("SELECT nudges_sent FROM recoveries WHERE id=?", (rid,)).fetchone()["nudges_sent"]
    con.commit()
    con.close()
    return n


def set_recovery_status(path, rid, status):
    con = _conn(path)
    con.execute(
        "UPDATE recoveries SET status=?, updated_at=? WHERE id=?", (status, now(), rid)
    )
    con.commit()
    con.close()


def get_recoveries(path):
    con = _conn(path)
    rows = con.execute("SELECT * FROM recoveries ORDER BY id DESC").fetchall()
    con.close()
    return [dict(r) for r in rows]
