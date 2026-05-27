"""
GlowCheck — SQLite → Firebase Firestore Migration
──────────────────────────────────────────────────
Firestore 컬렉션 구조 (플랫):
  /products/{productId}     — 공개 읽기
  /brands/{brandSlug}       — 공개 읽기 (브랜드 메타데이터)
  /ingredients/{id}         — 공개 읽기
  /reviews/{reviewId}       — 공개 읽기, 로그인 시 쓰기
  /users/{uid}/...          — 비공개

Usage:
  python firebase_migrate.py            # Firestore only
  python firebase_migrate.py --images   # Firestore + Storage image upload

Storage rules (add to Firebase console):
  match /product_images/{allPaths=**} {
    allow read: if true;
    allow write: if request.auth != null;
  }
  match /skin_photos/{uid}/{allPaths=**} {
    allow read, write: if request.auth.uid == uid;
  }
"""

import io
import os
import re
import sys
import time
import requests
import firebase_admin
from firebase_admin import credentials, firestore, storage as fb_storage
from database import get_db

STORAGE_BUCKET = 'glowcheck-b8a8e.firebasestorage.app'

CONCERN_INGREDIENTS = {
    'dry_skin':        ['alcohol denat', 'isopropyl alcohol', 'sd alcohol',
                        'sodium lauryl sulfate', 'ammonium lauryl sulfate'],
    'acne_prone':      ['coconut oil', 'cocoa butter', 'isopropyl myristate',
                        'isopropyl palmitate', 'sodium lauryl sulfate', 'mineral oil', 'lanolin'],
    'eczema_atopic':   ['fragrance', 'parfum', 'methylisothiazolinone',
                        'methylchloroisothiazolinone', 'dmdm hydantoin',
                        'propylene glycol', 'cocamidopropyl betaine'],
    'rosacea':         ['alcohol denat', 'witch hazel', 'menthol', 'peppermint',
                        'fragrance', 'parfum', 'sodium lauryl sulfate'],
    'sun_sensitive':   ['glycolic acid', 'lactic acid', 'retinol', 'retinyl palmitate',
                        'salicylic acid', 'mandelic acid'],
    'acid_sensitive':  ['glycolic acid', 'lactic acid', 'citric acid', 'malic acid',
                        'salicylic acid', 'mandelic acid', 'azelaic acid'],
    'fine_hair':       ['dimethicone', 'cyclopentasiloxane', 'cyclohexasiloxane',
                        'mineral oil', 'petrolatum', 'castor oil'],
    'hair_loss':       ['sodium lauryl sulfate', 'ammonium lauryl sulfate',
                        'ammonium laureth sulfate', 'sodium laureth sulfate'],
    'scalp_sensitive': ['fragrance', 'parfum', 'methylisothiazolinone',
                        'sodium lauryl sulfate', 'ammonium lauryl sulfate'],
    'curly_hair':      ['sodium lauryl sulfate', 'ammonium lauryl sulfate',
                        'isopropyl alcohol', 'alcohol denat', 'sd alcohol'],
}

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'GlowCheckBot/1.0'})


def ingredient_concerns(name: str) -> list[str]:
    name_lower = name.lower()
    return [c for c, patterns in CONCERN_INGREDIENTS.items()
            if any(p in name_lower for p in patterns)]


def safe_slug(name: str, fallback_id: int | None = None) -> str:
    slug = re.sub(r'[^a-z0-9]', '_', name.lower().strip())
    slug = re.sub(r'_+', '_', slug).strip('_')   # collapse & strip underscores
    slug = slug[:100]
    if not slug or slug.startswith('__'):
        # Firestore reserves IDs that are all-underscore or start with __
        slug = f"ing_{fallback_id}" if fallback_id is not None else f"ing_{abs(hash(name)) % 1_000_000}"
    return slug


def batch_write(db_fs, collection: str, docs: list[tuple], batch_size: int = 400):
    """docs = [(doc_id, data_dict), ...]"""
    batches = [docs[i:i+batch_size] for i in range(0, len(docs), batch_size)]
    total = 0
    for chunk in batches:
        batch = db_fs.batch()
        for doc_id, data in chunk:
            ref = db_fs.collection(collection).document(str(doc_id))
            batch.set(ref, data)
        batch.commit()
        total += len(chunk)
        print(f"  [{collection}] {total}/{len(docs)} 저장됨")


def clear_collection(db_fs, collection: str, batch_size: int = 400):
    """컬렉션 최상위 문서 전체 삭제"""
    print(f"  기존 [{collection}] 삭제 중...")
    total = 0
    while True:
        docs = list(db_fs.collection(collection).limit(batch_size).stream())
        if not docs:
            break
        batch = db_fs.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
        total += len(docs)
    print(f"  {total}개 문서 삭제 완료.")


# ── Storage image upload ──────────────────────────────────────────────────────

def storage_public_url(bucket_name: str, blob_path: str) -> str:
    """Returns the public read URL for a blob (requires Storage rules allow read: true)."""
    encoded = blob_path.replace('/', '%2F')
    return f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded}?alt=media"


def upload_product_image(bucket, product_id: str, src_url: str) -> str | None:
    """
    Downloads image from src_url and uploads to Storage at product_images/{product_id}.jpg
    Returns the public Storage URL, or None on failure.
    """
    if not src_url or not src_url.startswith('http'):
        return None
    try:
        resp = SESSION.get(src_url, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get('content-type', 'image/jpeg').split(';')[0].strip()
        ext = 'jpg' if 'jpeg' in content_type or 'jpg' in content_type else \
              'png' if 'png' in content_type else \
              'webp' if 'webp' in content_type else 'jpg'

        blob_path = f"product_images/{product_id}.{ext}"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(resp.content, content_type=content_type)

        return storage_public_url(STORAGE_BUCKET, blob_path)
    except Exception as e:
        print(f"    [warn] image upload failed for product {product_id}: {e}")
        return None


def migrate_images(db_fs, bucket):
    """
    Pass 4 (optional): For every product in Firestore that has a non-Storage image_url,
    upload the image to Storage and update the Firestore doc.
    """
    print("\n=== [4/4] Product images → Firebase Storage ===")
    col = db_fs.collection('products')
    docs = list(col.stream())
    updated = 0
    skipped = 0

    for doc in docs:
        data = doc.to_dict()
        src_url = data.get('image_url') or ''

        # Skip if already in Storage or no URL
        if not src_url or 'firebasestorage.googleapis.com' in src_url:
            skipped += 1
            continue

        pid = doc.id
        storage_url = upload_product_image(bucket, pid, src_url)
        if storage_url:
            col.document(pid).update({'image_url': storage_url})
            updated += 1
            if updated % 20 == 0:
                print(f"  {updated} images uploaded...")
        else:
            skipped += 1

        time.sleep(0.1)   # rate-limit

    print(f"  이미지 완료: {updated}개 업로드, {skipped}개 스킵")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    upload_images = '--images' in sys.argv

    key_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
    if not os.path.exists(key_path):
        print("ERROR: serviceAccountKey.json 을 찾을 수 없습니다.")
        sys.exit(1)

    cred = credentials.Certificate(key_path)
    init_kwargs = {'storageBucket': STORAGE_BUCKET} if upload_images else {}
    firebase_admin.initialize_app(cred, init_kwargs)
    db_fs = firestore.client()

    conn = get_db()
    c    = conn.cursor()

    # ── 1. Ingredients ────────────────────────────────────────────────────
    print("\n=== [1/3] Ingredients 이관 중... ===")
    rows = c.execute("SELECT * FROM ingredients").fetchall()
    ing_sqlite_to_slug: dict[int, str] = {}
    ing_docs = []

    for row in rows:
        r = dict(row)
        slug = safe_slug(r['name'], fallback_id=r['id'])
        ing_sqlite_to_slug[r['id']] = slug
        ing_docs.append((slug, {
            'name':        r['name'],
            'inci_name':   r.get('inci_name') or '',
            'ewg_score':   r.get('ewg_score'),
            'ewg_url':     r.get('ewg_url') or '',
            'function':    r.get('function') or '',
            'description': r.get('description') or '',
            'concerns':    ingredient_concerns(r['name']),
        }))

    clear_collection(db_fs, 'ingredients')
    batch_write(db_fs, 'ingredients', ing_docs)
    print(f"총 {len(ing_docs)}개 성분 완료.")

    # ── 2. Products ───────────────────────────────────────────────────────
    print("\n=== [2/3] Products 이관 중 (flat 구조)... ===")
    clear_collection(db_fs, 'products')

    products = c.execute("SELECT * FROM products").fetchall()
    prod_docs   = []
    brand_meta: dict[str, dict] = {}

    for prod in products:
        p   = dict(prod)
        pid = str(p['id'])

        brand      = p.get('brand') or 'Unknown'
        category   = p.get('category') or 'other'
        brand_slug = safe_slug(brand)

        ings = c.execute("""
            SELECT i.id, i.name, i.ewg_score, i.function, pi.position
            FROM product_ingredients pi
            JOIN ingredients i ON i.id = pi.ingredient_id
            WHERE pi.product_id = ?
            ORDER BY pi.position
        """, (pid,)).fetchall()

        ing_names = [dict(i)['name'] for i in ings]
        ing_slugs = [ing_sqlite_to_slug.get(dict(i)['id'], safe_slug(dict(i)['name'])) for i in ings]
        ing_ewg   = [dict(i)['ewg_score'] for i in ings]
        ing_func  = [dict(i)['function'] or '' for i in ings]
        ing_pos   = [dict(i)['position'] for i in ings]

        valid_scores = [s for s in ing_ewg if s is not None]
        avg_ewg      = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else None

        triggered: set[str] = set()
        for name in ing_names:
            triggered.update(ingredient_concerns(name))

        prod_docs.append((pid, {
            'id':                 pid,
            'name':               p['name'],
            'brand':              brand,
            'brand_slug':         brand_slug,
            'category':           category,
            'subcategory':        p.get('subcategory') or '',
            'price':              p.get('price') or 0,
            'retailer':           p.get('retailer') or '',
            'rating':             p.get('rating') or 0,
            'review_count':       0,
            'avg_rating':         0,
            'image_url':          p.get('image_url') or '',
            'product_url':        p.get('product_url') or '',
            'avg_ewg':            avg_ewg,
            'triggered_concerns': sorted(triggered),
            'ingredient_names':   ing_names,
            'ingredient_doc_ids': ing_slugs,
            'ingredient_ewg':     ing_ewg,
            'ingredient_func':    ing_func,
            'ingredient_pos':     ing_pos,
        }))

        if brand_slug not in brand_meta:
            brand_meta[brand_slug] = {
                'name': brand, 'slug': brand_slug,
                'categories': set(), 'product_count': 0,
            }
        brand_meta[brand_slug]['categories'].add(category)
        brand_meta[brand_slug]['product_count'] += 1

    batch_write(db_fs, 'products', prod_docs)
    print(f"총 {len(prod_docs)}개 제품 완료.")

    # ── 3. Brands ─────────────────────────────────────────────────────────
    print("\n=== [3/3] Brands 이관 중... ===")
    clear_collection(db_fs, 'brands')
    brand_docs = []
    for slug, meta in brand_meta.items():
        meta['categories'] = sorted(meta['categories'])
        brand_docs.append((slug, meta))
    batch_write(db_fs, 'brands', brand_docs)
    print(f"총 {len(brand_docs)}개 브랜드 완료.")

    conn.close()

    # ── 4. Images (optional) ──────────────────────────────────────────────
    if upload_images:
        bucket = fb_storage.bucket()
        migrate_images(db_fs, bucket)

    print(f"\nDone! products {len(prod_docs)}, ingredients {len(ing_docs)}, brands {len(brand_docs)}")
    if not upload_images:
        print("  이미지도 Storage에 올리려면: python firebase_migrate.py --images")
    print("\n쿼리 예시:")
    print("  카테고리별: db.collection('products').where('category','==','skincare')")
    print("  브랜드별:   db.collection('products').where('brand_slug','==','cerave')")
    print("  둘 다:      db.collection('products').where('brand_slug','==','cerave').where('category','==','skincare')")


if __name__ == '__main__':
    main()
