import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'glowcheck.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    c = conn.cursor()

    # ---------- Ingredients ----------
    c.execute('''
        CREATE TABLE IF NOT EXISTS ingredients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            inci_name   TEXT,
            ewg_score   INTEGER,          -- 1(safest) ~ 10(hazardous)
            ewg_url     TEXT,
            function    TEXT,             -- e.g. "Moisturizer, Emollient"
            description TEXT,
            concerns    TEXT,             -- JSON array string
            skin_types  TEXT,             -- JSON array string
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ---------- Products ----------
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            brand       TEXT,
            category    TEXT,             -- skincare | makeup | suncare | haircare
            subcategory TEXT,             -- moisturizer | foundation | ...
            price       REAL,
            currency    TEXT DEFAULT 'USD',
            image_url   TEXT,
            product_url TEXT,
            retailer    TEXT,             -- sephora | ulta | amazon
            rating      REAL,
            review_count INTEGER,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ---------- Product ↔ Ingredient (many-to-many) ----------
    c.execute('''
        CREATE TABLE IF NOT EXISTS product_ingredients (
            product_id    INTEGER REFERENCES products(id),
            ingredient_id INTEGER REFERENCES ingredients(id),
            position      INTEGER,        -- order in the INCI list
            PRIMARY KEY (product_id, ingredient_id)
        )
    ''')

    # ---------- Crawl log ----------
    c.execute('''
        CREATE TABLE IF NOT EXISTS crawl_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            source     TEXT,
            status     TEXT,
            records    INTEGER,
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("[DB] Tables ready.")


if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
