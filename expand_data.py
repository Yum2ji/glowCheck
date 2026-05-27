"""
GlowCheck — Open Beauty Facts bulk import
Fetches 500+ products and upserts them into the local SQLite DB.

Usage:
    python expand_data.py

Open Beauty Facts API docs: https://wiki.openfoodfacts.org/API
"""

import re
import sys
import time
import json
import sqlite3
import requests
from database import get_db, init_db

# ── Category mapping ────────────────────────────────────────────────────────
CATEGORY_MAP = [
    # (obf_tag,                   category,    subcategory)
    ('en:face-creams',            'skincare',   'moisturizer'),
    ('en:moisturizers',           'skincare',   'moisturizer'),
    ('en:face-moisturizers',      'skincare',   'moisturizer'),
    ('en:serums',                 'skincare',   'serum'),
    ('en:facial-serums',          'skincare',   'serum'),
    ('en:facial-cleansers',       'skincare',   'cleanser'),
    ('en:face-washes',            'skincare',   'cleanser'),
    ('en:toners',                 'skincare',   'toner'),
    ('en:facial-toners',          'skincare',   'toner'),
    ('en:eye-creams',             'skincare',   'eye cream'),
    ('en:face-masks',             'skincare',   'mask'),
    ('en:sheet-masks',            'skincare',   'mask'),
    ('en:foundations',            'makeup',     'foundation'),
    ('en:bb-creams',              'makeup',     'bb cream'),
    ('en:concealers',             'makeup',     'concealer'),
    ('en:lipsticks',              'makeup',     'lipstick'),
    ('en:lip-glosses',            'makeup',     'lip gloss'),
    ('en:mascaras',               'makeup',     'mascara'),
    ('en:eyeshadows',             'makeup',     'eyeshadow'),
    ('en:shampoos',               'haircare',   'shampoo'),
    ('en:conditioners',           'haircare',   'conditioner'),
    ('en:hair-masks',             'haircare',   'hair mask'),
    ('en:sunscreens',             'suncare',    'sunscreen'),
    ('en:sun-creams',             'suncare',    'sunscreen'),
    ('en:spf-moisturizers',       'suncare',    'sunscreen'),
]

FIELDS = ','.join([
    'code', 'product_name', 'brands', 'categories_tags',
    'ingredients_text', 'ingredients',
    'image_url', 'image_front_url',
    'url', 'product_quantity',
])

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'GlowCheckBot/1.0 (wda9347@gmail.com)'})


# ── Helpers ──────────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip()).strip('., ')


def parse_ingredient_names(product: dict) -> list[str]:
    """
    Try structured ingredients list first, fall back to text parsing.
    Returns a list of normalized ingredient name strings.
    """
    structured = product.get('ingredients') or []
    if structured:
        names = []
        for ing in structured:
            n = ing.get('text') or ing.get('id') or ''
            n = re.sub(r'^en:', '', n)
            n = normalize(n)
            if n and len(n) < 120:
                names.append(n)
        if names:
            return names

    raw = product.get('ingredients_text') or ''
    if not raw:
        return []

    # Strip HTML, split on common delimiters
    raw = re.sub(r'<[^>]+>', '', raw)
    raw = re.sub(r'\([\d.]+%\)', '', raw)           # remove percentages like (1.5%)
    raw = re.sub(r'\[[^\]]*\]', '', raw)             # remove bracketed notes
    parts = re.split(r'[,;/]', raw)
    names = []
    for p in parts:
        n = normalize(p)
        n = re.sub(r'^[\-•·\*\d\.]+\s*', '', n)     # strip bullets/numbers
        if n and 2 < len(n) < 120:
            names.append(n)
    return names


def infer_category(product: dict):
    """Return (category, subcategory) from categories_tags."""
    tags = set(product.get('categories_tags') or [])
    for tag, cat, sub in CATEGORY_MAP:
        if tag in tags:
            return cat, sub
    return None, None


def fetch_page(tag: str, page: int, page_size: int = 50) -> list[dict]:
    url = 'https://world.openbeautyfacts.org/api/v2/search'
    params = {
        'categories_tags': tag,
        'fields': FIELDS,
        'page_size': page_size,
        'page': page,
        'sort_by': 'unique_scans_n',
    }
    try:
        resp = SESSION.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data.get('products') or []
    except Exception as e:
        print(f"  [warn] fetch error page {page} for {tag}: {e}")
        return []


# ── DB upsert ─────────────────────────────────────────────────────────────────

def upsert_ingredient(cur: sqlite3.Cursor, name: str) -> int:
    """Insert ingredient if not exists, return its id."""
    cur.execute('SELECT id FROM ingredients WHERE lower(name) = lower(?)', (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        'INSERT INTO ingredients (name) VALUES (?)',
        (name,)
    )
    return cur.lastrowid


def upsert_product(cur: sqlite3.Cursor, p: dict, category: str, subcategory: str) -> int | None:
    """
    Insert product if (name, brand) not already present.
    Returns product id or None if skipped.
    """
    name  = normalize(p.get('product_name') or '').title()
    brand = normalize(p.get('brands') or '').split(',')[0].strip().title()

    if not name or len(name) < 3:
        return None

    cur.execute(
        'SELECT id FROM products WHERE lower(name)=lower(?) AND lower(COALESCE(brand,""))=lower(?)',
        (name, brand)
    )
    existing = cur.fetchone()
    if existing:
        return existing[0]

    image_url = (p.get('image_front_url') or p.get('image_url') or '').strip()
    product_url = (p.get('url') or '').strip()

    cur.execute('''
        INSERT INTO products (name, brand, category, subcategory, image_url, product_url, retailer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (name, brand, category, subcategory, image_url, product_url, 'openbeautyfacts'))
    return cur.lastrowid


def link_ingredients(cur: sqlite3.Cursor, product_id: int, ing_names: list[str]):
    for pos, name in enumerate(ing_names, start=1):
        if not name:
            continue
        ing_id = upsert_ingredient(cur, name)
        cur.execute('''
            INSERT OR IGNORE INTO product_ingredients (product_id, ingredient_id, position)
            VALUES (?, ?, ?)
        ''', (product_id, ing_id, pos))


# ── Main ──────────────────────────────────────────────────────────────────────

TARGET = 600   # fetch at least this many unique products


def main():
    init_db()
    conn = get_db()
    cur  = conn.cursor()

    cur.execute('SELECT COUNT(*) FROM products')
    before = cur.fetchone()[0]
    print(f"DB products before: {before}")

    inserted = 0
    seen_codes: set[str] = set()

    for tag, category, subcategory in CATEGORY_MAP:
        if inserted >= TARGET:
            break

        print(f"\n→ {tag}  ({category}/{subcategory})")
        for page in range(1, 6):          # up to 5 pages × 50 = 250 per category
            if inserted >= TARGET:
                break

            products = fetch_page(tag, page)
            if not products:
                break

            for p in products:
                code = p.get('code') or ''
                if code and code in seen_codes:
                    continue
                if code:
                    seen_codes.add(code)

                ing_names = parse_ingredient_names(p)
                if not ing_names:
                    continue            # skip products with no ingredient data

                pid = upsert_product(cur, p, category, subcategory)
                if pid is None:
                    continue

                link_ingredients(cur, pid, ing_names)
                inserted += 1

                if inserted % 50 == 0:
                    conn.commit()
                    print(f"  {inserted} products saved so far...")

            time.sleep(0.5)             # be polite to the API

    conn.commit()

    cur.execute('SELECT COUNT(*) FROM products')
    after = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM ingredients')
    ing_count = cur.fetchone()[0]
    conn.close()

    print(f"\nDone! +{after - before} new products (total {after}), {ing_count} unique ingredients.")
    print("Next: run  python firebase_migrate.py  to push to Firestore.")


if __name__ == '__main__':
    main()
