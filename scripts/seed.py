"""Seed the demo catalog. Run from repo root:  python scripts/seed.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, db

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

if __name__ == "__main__":
    db.init_db(config.DB_PATH)
    existing = {p["name"] for p in db.get_products(config.DB_PATH)}
    added = 0
    for name, price, cat, desc in PRODUCTS:
        if name not in existing:
            db.add_product(config.DB_PATH, name, price, cat, desc)
            added += 1
    print(f"catalog ready: {added} new, {len(existing)} existing products in {config.DB_PATH}")
