"""
GlowCheck – US Cosmetic Ingredient Transparency App
Flask Backend  |  API v1
"""

from flask import Flask, jsonify, request, render_template, abort
from flask_cors import CORS
import sqlite3
import json
import os

from database import get_db, init_db, DB_PATH

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────────────────
# Skin & Hair concern → ingredient mapping
# ─────────────────────────────────────────────────────────

CONCERN_INGREDIENTS = {
    'dry_skin':       ['alcohol denat', 'isopropyl alcohol', 'sd alcohol',
                       'sodium lauryl sulfate', 'ammonium lauryl sulfate'],
    'acne_prone':     ['coconut oil', 'cocoa butter', 'isopropyl myristate',
                       'isopropyl palmitate', 'sodium lauryl sulfate', 'mineral oil', 'lanolin'],
    'eczema_atopic':  ['fragrance', 'parfum', 'methylisothiazolinone',
                       'methylchloroisothiazolinone', 'dmdm hydantoin',
                       'propylene glycol', 'cocamidopropyl betaine'],
    'rosacea':        ['alcohol denat', 'witch hazel', 'menthol', 'peppermint',
                       'fragrance', 'parfum', 'sodium lauryl sulfate'],
    'sun_sensitive':  ['glycolic acid', 'lactic acid', 'retinol', 'retinyl palmitate',
                       'salicylic acid', 'mandelic acid'],
    'acid_sensitive': ['glycolic acid', 'lactic acid', 'citric acid', 'malic acid',
                       'salicylic acid', 'mandelic acid', 'azelaic acid'],
    'fine_hair':      ['dimethicone', 'cyclopentasiloxane', 'cyclohexasiloxane',
                       'mineral oil', 'petrolatum', 'castor oil'],
    'hair_loss':      ['sodium lauryl sulfate', 'ammonium lauryl sulfate',
                       'ammonium laureth sulfate', 'sodium laureth sulfate'],
    'scalp_sensitive':['fragrance', 'parfum', 'methylisothiazolinone',
                       'sodium lauryl sulfate', 'ammonium lauryl sulfate'],
    'curly_hair':     ['sodium lauryl sulfate', 'ammonium lauryl sulfate',
                       'isopropyl alcohol', 'alcohol denat', 'sd alcohol'],
}

CONCERN_META = {
    'skin': [
        {'id': 'dry_skin',       'label': 'Dry Skin',          'desc': 'Avoids drying alcohols & harsh sulfates'},
        {'id': 'acne_prone',     'label': 'Acne-prone',        'desc': 'Avoids comedogenic oils & pore-cloggers'},
        {'id': 'eczema_atopic',  'label': 'Eczema / Atopic',   'desc': 'Avoids fragrance, MIT, and irritant preservatives'},
        {'id': 'rosacea',        'label': 'Rosacea',           'desc': 'Avoids alcohol, menthol, fragrance, witch hazel'},
        {'id': 'sun_sensitive',  'label': 'Sun-sensitive',     'desc': 'Avoids AHAs, retinol, photosensitizing acids'},
        {'id': 'acid_sensitive', 'label': 'Acid-sensitive',    'desc': 'Avoids AHAs, BHAs, and acid exfoliants'},
    ],
    'hair': [
        {'id': 'fine_hair',        'label': 'Fine / Thin hair',   'desc': 'Avoids heavy silicones, mineral oil, castor oil'},
        {'id': 'hair_loss',        'label': 'Hair Loss / Thinning','desc': 'Avoids harsh sulfates that strip scalp'},
        {'id': 'scalp_sensitive',  'label': 'Sensitive Scalp',    'desc': 'Avoids fragrance, MIT, harsh sulfates'},
        {'id': 'curly_hair',       'label': 'Curly / Coily hair', 'desc': 'Avoids sulfates and drying alcohols'},
    ],
}


# ─────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────

def rows_to_list(rows):
    return [dict(r) for r in rows]


def _build_avoid_filter(avoid_concerns: str, avoid_ingredients: str):
    """Returns (sql_fragment, params_list) for NOT IN subquery, or ('', [])."""
    like_parts, params = [], []

    if avoid_concerns:
        for ck in avoid_concerns.split(','):
            ck = ck.strip()
            for ing in CONCERN_INGREDIENTS.get(ck, []):
                like_parts.append('LOWER(i2.name) LIKE ?')
                params.append(f'%{ing}%')

    if avoid_ingredients:
        for ing in avoid_ingredients.split(','):
            ing = ing.strip()
            if ing:
                like_parts.append('LOWER(i2.name) LIKE ?')
                params.append(f'%{ing.lower()}%')

    if not like_parts:
        return '', []

    where = ' OR '.join(like_parts)
    sql = f"""p.id NOT IN (
        SELECT DISTINCT pi2.product_id
        FROM product_ingredients pi2
        JOIN ingredients i2 ON i2.id = pi2.ingredient_id
        WHERE {where}
    )"""
    return sql, params


# ─────────────────────────────────────────────────────────
# Pages
# ─────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ─────────────────────────────────────────────────────────
# API: Products
# ─────────────────────────────────────────────────────────

@app.route('/api/products', methods=['GET'])
def get_products():
    """Search & filter products."""
    q          = request.args.get('q', '').strip()
    category   = request.args.get('category', '').strip()
    subcategory = request.args.get('subcategory', '').strip()
    retailer   = request.args.get('retailer', '').strip()
    min_price         = request.args.get('min_price', type=float)
    max_price         = request.args.get('max_price', type=float)
    min_ewg           = request.args.get('min_ewg', type=float)
    max_ewg           = request.args.get('max_ewg', type=float)
    avoid_concerns    = request.args.get('avoid_concerns', '').strip()
    avoid_ingredients = request.args.get('avoid_ingredients', '').strip()
    sort              = request.args.get('sort', 'rating')
    page       = request.args.get('page', 1, type=int)
    per_page   = request.args.get('per_page', 24, type=int)

    filters = []
    params  = []

    if q:
        filters.append("(p.name LIKE ? OR p.brand LIKE ?)")
        params += [f'%{q}%', f'%{q}%']
    if category:
        filters.append("p.category = ?")
        params.append(category)
    if subcategory:
        filters.append("p.subcategory = ?")
        params.append(subcategory)
    if retailer:
        filters.append("p.retailer = ?")
        params.append(retailer)
    if min_price is not None:
        filters.append("p.price >= ?")
        params.append(min_price)
    if max_price is not None:
        filters.append("p.price <= ?")
        params.append(max_price)

    avoid_sql, avoid_params = _build_avoid_filter(avoid_concerns, avoid_ingredients)
    if avoid_sql:
        filters.append(avoid_sql)
        params.extend(avoid_params)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    having_filters = []
    having_params  = []
    if min_ewg is not None:
        having_filters.append("avg_ewg >= ?")
        having_params.append(min_ewg)
    if max_ewg is not None:
        having_filters.append("avg_ewg <= ?")
        having_params.append(max_ewg)
    having = ("HAVING " + " AND ".join(having_filters)) if having_filters else ""

    order_map = {
        'rating'     : 'p.rating DESC',
        'price_asc'  : 'p.price ASC',
        'price_desc' : 'p.price DESC',
        'name'       : 'p.name ASC',
    }
    order = order_map.get(sort, 'p.rating DESC')

    offset = (page - 1) * per_page

    conn = get_db()
    c    = conn.cursor()

    count_sql = f"""
        SELECT COUNT(*) FROM (
            SELECT p.id, ROUND(AVG(i.ewg_score), 1) AS avg_ewg
            FROM products p
            LEFT JOIN product_ingredients pi ON pi.product_id = p.id
            LEFT JOIN ingredients i          ON i.id = pi.ingredient_id
            {where}
            GROUP BY p.id
            {having}
        )
    """
    total = c.execute(count_sql, params + having_params).fetchone()[0]

    sql = f"""
        SELECT p.*,
               ROUND(AVG(i.ewg_score), 1) AS avg_ewg
        FROM   products p
        LEFT JOIN product_ingredients pi ON pi.product_id = p.id
        LEFT JOIN ingredients i          ON i.id = pi.ingredient_id
        {where}
        GROUP BY p.id
        {having}
        ORDER BY {order}
        LIMIT ? OFFSET ?
    """
    rows = c.execute(sql, params + having_params + [per_page, offset]).fetchall()
    conn.close()

    return jsonify({
        'total'    : total,
        'page'     : page,
        'per_page' : per_page,
        'products' : rows_to_list(rows),
    })


@app.route('/api/concerns')
def get_concerns():
    return jsonify(CONCERN_META)


@app.route('/api/products/<int:pid>', methods=['GET'])
def get_product(pid):
    """Product detail with full ingredient list."""
    conn = get_db()
    c    = conn.cursor()

    product = c.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if not product:
        conn.close()
        abort(404)

    ingredients = c.execute("""
        SELECT i.*, pi.position
        FROM   ingredients i
        JOIN   product_ingredients pi ON pi.ingredient_id = i.id
        WHERE  pi.product_id = ?
        ORDER  BY pi.position
    """, (pid,)).fetchall()

    conn.close()

    result = dict(product)
    result['ingredients'] = rows_to_list(ingredients)

    # Overall EWG summary
    scores = [row['ewg_score'] for row in ingredients if row['ewg_score']]
    if scores:
        result['avg_ewg']  = round(sum(scores) / len(scores), 1)
        result['max_ewg']  = max(scores)
    else:
        result['avg_ewg']  = None
        result['max_ewg']  = None

    return jsonify(result)


@app.route('/api/products/compare', methods=['GET'])
def compare_products():
    """Compare multiple products side-by-side."""
    ids_raw = request.args.get('ids', '')
    try:
        ids = [int(x) for x in ids_raw.split(',') if x.strip()]
    except ValueError:
        return jsonify({'error': 'Invalid ids parameter'}), 400

    if len(ids) < 2 or len(ids) > 4:
        return jsonify({'error': 'Provide 2–4 product IDs'}), 400

    conn = get_db()
    c    = conn.cursor()
    results = []

    for pid in ids:
        product = c.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if not product:
            continue
        ingredients = c.execute("""
            SELECT i.*, pi.position
            FROM   ingredients i
            JOIN   product_ingredients pi ON pi.ingredient_id = i.id
            WHERE  pi.product_id = ?
            ORDER  BY pi.position
        """, (pid,)).fetchall()
        d = dict(product)
        d['ingredients'] = rows_to_list(ingredients)
        scores = [r['ewg_score'] for r in ingredients if r['ewg_score']]
        d['avg_ewg'] = round(sum(scores)/len(scores), 1) if scores else None
        results.append(d)

    conn.close()
    return jsonify({'products': results})


# ─────────────────────────────────────────────────────────
# API: Ingredients
# ─────────────────────────────────────────────────────────

@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    q         = request.args.get('q', '').strip()
    min_score = request.args.get('min_score', type=int)
    max_score = request.args.get('max_score', type=int)
    page      = request.args.get('page', 1, type=int)
    per_page  = request.args.get('per_page', 30, type=int)

    filters = []
    params  = []
    if q:
        filters.append("(name LIKE ? OR inci_name LIKE ? OR function LIKE ?)")
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if min_score is not None:
        filters.append("ewg_score >= ?")
        params.append(min_score)
    if max_score is not None:
        filters.append("ewg_score <= ?")
        params.append(max_score)

    where  = ("WHERE " + " AND ".join(filters)) if filters else ""
    offset = (page - 1) * per_page

    conn   = get_db()
    c      = conn.cursor()
    total  = c.execute(f"SELECT COUNT(*) FROM ingredients {where}", params).fetchone()[0]
    rows   = c.execute(f"SELECT * FROM ingredients {where} ORDER BY ewg_score ASC LIMIT ? OFFSET ?",
                        params + [per_page, offset]).fetchall()
    conn.close()

    return jsonify({'total': total, 'page': page, 'ingredients': rows_to_list(rows)})


@app.route('/api/ingredients/<int:iid>', methods=['GET'])
def get_ingredient(iid):
    conn = get_db()
    ingredient = conn.execute("SELECT * FROM ingredients WHERE id = ?", (iid,)).fetchone()
    if not ingredient:
        conn.close()
        abort(404)

    # products that contain this ingredient
    products = conn.execute("""
        SELECT p.id, p.name, p.brand, p.category, p.price, p.image_url, p.rating
        FROM   products p
        JOIN   product_ingredients pi ON pi.product_id = p.id
        WHERE  pi.ingredient_id = ?
        ORDER  BY p.rating DESC
        LIMIT 20
    """, (iid,)).fetchall()

    conn.close()
    result = dict(ingredient)
    result['products'] = rows_to_list(products)
    return jsonify(result)


# ─────────────────────────────────────────────────────────
# API: Categories
# ─────────────────────────────────────────────────────────

@app.route('/api/categories', methods=['GET'])
def get_categories():
    conn = get_db()
    rows = conn.execute("""
        SELECT category, subcategory, COUNT(*) as count
        FROM   products
        GROUP  BY category, subcategory
        ORDER  BY category, count DESC
    """).fetchall()
    conn.close()

    # Build nested dict
    cats = {}
    for r in rows:
        cat = r['category'] or 'other'
        sub = r['subcategory'] or 'other'
        cats.setdefault(cat, {})[sub] = r['count']

    return jsonify(cats)


# ─────────────────────────────────────────────────────────
# API: Stats
# ─────────────────────────────────────────────────────────

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    c    = conn.cursor()
    stats = {
        'total_products'   : c.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        'total_ingredients': c.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0],
        'brands'           : c.execute("SELECT COUNT(DISTINCT brand) FROM products").fetchone()[0],
        'avg_ewg'          : c.execute("SELECT ROUND(AVG(ewg_score),1) FROM ingredients WHERE ewg_score IS NOT NULL").fetchone()[0],
    }
    conn.close()
    return jsonify(stats)


# ─────────────────────────────────────────────────────────
# API: Crawl trigger (manual)
# ─────────────────────────────────────────────────────────

@app.route('/api/crawl', methods=['POST'])
def trigger_crawl():
    source = request.json.get('source', 'all')
    try:
        from crawler import run_crawl
        result = run_crawl(source)
        return jsonify({'status': 'ok', 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
