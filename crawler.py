"""
GlowCheck Crawler
─────────────────
Scrapes product & ingredient data from:
  1. EWG Skin Deep  – ingredient safety scores
  2. Sephora        – products & prices
  3. Ulta           – products & prices

Usage:
    python crawler.py              # run all crawlers
    python crawler.py ewg          # EWG only
    python crawler.py sephora      # Sephora only
    python crawler.py ulta         # Ulta only
"""

import requests
import json
import time
import sys
import os
import random
from bs4 import BeautifulSoup
from database import get_db, init_db, DB_PATH

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}


def sleep_rand(lo=1.0, hi=3.0):
    time.sleep(random.uniform(lo, hi))


# ═══════════════════════════════════════════════════════════
# 1. EWG Skin Deep – ingredient safety scores
# ═══════════════════════════════════════════════════════════

EWG_SEARCH = "https://www.ewg.org/skindeep/search/?search={}"

def crawl_ewg_ingredient(name: str) -> dict | None:
    """Fetch EWG safety score for a single ingredient by name."""
    try:
        url = EWG_SEARCH.format(requests.utils.quote(name))
        r   = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'lxml')

        # First result card
        card = soup.select_one('.ingredient-result, .search-result-item')
        if not card:
            return None

        score_el = card.select_one('.score, [class*="score"]')
        score    = int(score_el.text.strip()) if score_el else None

        name_el  = card.select_one('.ingredient-name, h3, h4')
        inci     = name_el.text.strip() if name_el else name

        link_el  = card.select_one('a[href*="/skindeep/ingredients/"]')
        ewg_url  = ('https://www.ewg.org' + link_el['href']) if link_el else None

        return {'name': name, 'inci_name': inci, 'ewg_score': score, 'ewg_url': ewg_url}
    except Exception as e:
        print(f"  [EWG] Error for '{name}': {e}")
        return None


def crawl_ewg_bulk(ingredient_names: list[str]) -> list[dict]:
    results = []
    for name in ingredient_names:
        data = crawl_ewg_ingredient(name)
        if data:
            results.append(data)
            print(f"  [EWG] {name} → score {data.get('ewg_score')}")
        sleep_rand(1, 2.5)
    return results


# ═══════════════════════════════════════════════════════════
# 2. Sephora – products, prices, ingredients
# ═══════════════════════════════════════════════════════════

SEPHORA_CATEGORIES = {
    'skincare': 'https://www.sephora.com/shop/skincare',
    'makeup'  : 'https://www.sephora.com/shop/makeup',
    'suncare' : 'https://www.sephora.com/shop/sun-protection',
}

def _parse_sephora_product(card) -> dict | None:
    try:
        name_el  = card.select_one('[data-comp="DisplayName"] span, .css-1pgnl76')
        brand_el = card.select_one('[data-comp="BrandName"] span, .css-ktoumz')
        price_el = card.select_one('[data-comp="Price"] span, .css-1nfmgm6')
        img_el   = card.select_one('img')
        link_el  = card.select_one('a[href]')

        name  = name_el.text.strip()  if name_el  else None
        brand = brand_el.text.strip() if brand_el else None
        price_raw = price_el.text.strip() if price_el else '0'
        price = float(price_raw.replace('$', '').replace(',', '').split('-')[0].strip() or 0)
        img   = img_el['src']         if img_el  else None
        url   = 'https://www.sephora.com' + link_el['href'] if link_el else None

        if not name:
            return None

        return {
            'name'       : name,
            'brand'      : brand,
            'price'      : price,
            'image_url'  : img,
            'product_url': url,
            'retailer'   : 'sephora',
        }
    except Exception:
        return None


def crawl_sephora(category: str = 'skincare', max_pages: int = 3) -> list[dict]:
    base_url = SEPHORA_CATEGORIES.get(category, SEPHORA_CATEGORIES['skincare'])
    products = []

    for page in range(1, max_pages + 1):
        url = f"{base_url}?currentPage={page}&pageSize=60&sortBy=BEST_SELLER"
        print(f"  [Sephora] {category} page {page} …")
        try:
            r    = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, 'lxml')
            cards = soup.select('[data-comp="ProductTile"], .css-12egk0t')

            if not cards:
                print("  [Sephora] No product cards found – possible JS-rendering.")
                break

            for card in cards:
                p = _parse_sephora_product(card)
                if p:
                    p['category'] = category
                    products.append(p)

            print(f"  [Sephora] +{len(cards)} cards (total {len(products)})")
            sleep_rand(2, 4)
        except Exception as e:
            print(f"  [Sephora] Error page {page}: {e}")
            break

    return products


# ═══════════════════════════════════════════════════════════
# 3. Ulta – products, prices
# ═══════════════════════════════════════════════════════════

ULTA_CATEGORIES = {
    'skincare': 'https://www.ulta.com/skin-care',
    'makeup'  : 'https://www.ulta.com/makeup',
    'suncare' : 'https://www.ulta.com/sun-care',
}

def crawl_ulta(category: str = 'skincare', max_pages: int = 2) -> list[dict]:
    base_url = ULTA_CATEGORIES.get(category, ULTA_CATEGORIES['skincare'])
    products = []

    for page in range(1, max_pages + 1):
        url = f"{base_url}?N=27ll&Nrpp=96&No={(page-1)*96}"
        print(f"  [Ulta] {category} page {page} …")
        try:
            r    = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, 'lxml')
            cards = soup.select('.ProductCard, .product-item')

            for card in cards:
                try:
                    name_el  = card.select_one('.ProductCard-name, .product-title')
                    brand_el = card.select_one('.ProductCard-brand, .product-brand')
                    price_el = card.select_one('.ProductCard-price, .product-price')
                    img_el   = card.select_one('img')
                    link_el  = card.select_one('a[href]')

                    name  = name_el.text.strip()  if name_el  else None
                    if not name:
                        continue
                    brand = brand_el.text.strip() if brand_el else None
                    price_raw = price_el.text.strip() if price_el else '0'
                    price = float(price_raw.replace('$','').replace(',','').split('-')[0].strip() or 0)
                    img   = img_el.get('src', img_el.get('data-src')) if img_el else None
                    url_p = link_el['href'] if link_el else None
                    if url_p and not url_p.startswith('http'):
                        url_p = 'https://www.ulta.com' + url_p

                    products.append({
                        'name'       : name,
                        'brand'      : brand,
                        'price'      : price,
                        'image_url'  : img,
                        'product_url': url_p,
                        'retailer'   : 'ulta',
                        'category'   : category,
                    })
                except Exception:
                    continue

            print(f"  [Ulta] +{len(cards)} cards (total {len(products)})")
            sleep_rand(2, 4)
        except Exception as e:
            print(f"  [Ulta] Error page {page}: {e}")
            break

    return products


# ═══════════════════════════════════════════════════════════
# DB helpers
# ═══════════════════════════════════════════════════════════

def upsert_ingredient(conn, data: dict) -> int:
    c = conn.cursor()
    existing = c.execute("SELECT id FROM ingredients WHERE name = ?", (data['name'],)).fetchone()
    if existing:
        c.execute("""
            UPDATE ingredients SET inci_name=?, ewg_score=?, ewg_url=?
            WHERE id=?
        """, (data.get('inci_name'), data.get('ewg_score'), data.get('ewg_url'), existing['id']))
        return existing['id']
    else:
        c.execute("""
            INSERT INTO ingredients (name, inci_name, ewg_score, ewg_url)
            VALUES (?, ?, ?, ?)
        """, (data['name'], data.get('inci_name'), data.get('ewg_score'), data.get('ewg_url')))
        return c.lastrowid


def insert_product(conn, data: dict) -> int:
    c = conn.cursor()
    c.execute("""
        INSERT INTO products (name, brand, category, subcategory, price, image_url, product_url, retailer)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('name'), data.get('brand'), data.get('category'),
        data.get('subcategory'), data.get('price'),
        data.get('image_url'), data.get('product_url'), data.get('retailer'),
    ))
    return c.lastrowid


def link_product_ingredient(conn, product_id: int, ingredient_id: int, position: int):
    try:
        conn.execute("""
            INSERT OR IGNORE INTO product_ingredients (product_id, ingredient_id, position)
            VALUES (?, ?, ?)
        """, (product_id, ingredient_id, position))
    except Exception:
        pass


def log_crawl(conn, source: str, status: str, records: int):
    conn.execute("""
        INSERT INTO crawl_log (source, status, records) VALUES (?, ?, ?)
    """, (source, status, records))


# ═══════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════

def run_crawl(source: str = 'all') -> dict:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
    conn = get_db()
    summary = {}

    if source in ('all', 'sephora'):
        total = 0
        for cat in ('skincare', 'makeup', 'suncare'):
            products = crawl_sephora(cat, max_pages=2)
            for p in products:
                pid = insert_product(conn, p)
                total += 1
            conn.commit()
        log_crawl(conn, 'sephora', 'ok', total)
        conn.commit()
        summary['sephora'] = total
        print(f"[Sephora] Saved {total} products.")

    if source in ('all', 'ulta'):
        total = 0
        for cat in ('skincare', 'makeup', 'suncare'):
            products = crawl_ulta(cat, max_pages=2)
            for p in products:
                pid = insert_product(conn, p)
                total += 1
            conn.commit()
        log_crawl(conn, 'ulta', 'ok', total)
        conn.commit()
        summary['ulta'] = total
        print(f"[Ulta] Saved {total} products.")

    if source in ('all', 'ewg'):
        # Pull ingredient names from products already in DB
        names = [r[0] for r in conn.execute(
            "SELECT DISTINCT name FROM ingredients WHERE ewg_score IS NULL LIMIT 50"
        ).fetchall()]
        if not names:
            # Fallback: seed common ingredient names
            names = COMMON_INGREDIENTS[:30]

        results = crawl_ewg_bulk(names)
        for ing in results:
            upsert_ingredient(conn, ing)
        conn.commit()
        log_crawl(conn, 'ewg', 'ok', len(results))
        conn.commit()
        summary['ewg'] = len(results)
        print(f"[EWG] Saved {len(results)} ingredient scores.")

    conn.close()
    return summary


# Common ingredients to seed EWG data if DB is empty
COMMON_INGREDIENTS = [
    'Water', 'Glycerin', 'Niacinamide', 'Hyaluronic Acid', 'Retinol',
    'Vitamin C', 'Salicylic Acid', 'Benzoyl Peroxide', 'Zinc Oxide',
    'Titanium Dioxide', 'Dimethicone', 'Cetearyl Alcohol', 'Shea Butter',
    'Jojoba Oil', 'Squalane', 'Lactic Acid', 'Kojic Acid', 'Alpha Arbutin',
    'Ceramide NP', 'Ceramide AP', 'Panthenol', 'Allantoin', 'Aloe Vera',
    'Green Tea Extract', 'Vitamin E', 'Ferulic Acid', 'Azelaic Acid',
    'Peptides', 'Collagen', 'Caffeine',
]


if __name__ == '__main__':
    source = sys.argv[1] if len(sys.argv) > 1 else 'all'
    print(f"Starting crawl: source={source}")
    result = run_crawl(source)
    print("Done:", result)
