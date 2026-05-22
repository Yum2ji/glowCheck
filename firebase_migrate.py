"""
GlowCheck — SQLite → Firebase Firestore Migration
──────────────────────────────────────────────────
사전 준비:
  1. pip install firebase-admin
  2. Firebase Console > Project Settings > Service Accounts > Generate new private key
     → serviceAccountKey.json 을 이 파일과 같은 폴더에 저장
  3. python firebase_migrate.py

Firestore 컬렉션 구조:
  /products/{id}        — 공개 (로그인 불필요)
  /ingredients/{id}     — 공개 (로그인 불필요)
  /users/{uid}/...      — 비공개 (로그인 필요, 추후 사용)

Firestore Security Rules (Firebase Console 에서 직접 적용):
  rules_version = '2';
  service cloud.firestore {
    match /databases/{database}/documents {
      match /products/{id}     { allow read: if true; allow write: if false; }
      match /ingredients/{id}  { allow read: if true; allow write: if false; }
      match /users/{uid}/{document=**} {
        allow read, write: if request.auth != null && request.auth.uid == uid;
      }
    }
  }

Firebase Storage Rules:
  rules_version = '2';
  service firebase.storage {
    match /b/{bucket}/o {
      match /products/{allPaths=**} { allow read: if true; allow write: if false; }
      match /users/{uid}/{allPaths=**} {
        allow read, write: if request.auth != null && request.auth.uid == uid;
      }
    }
  }
"""

import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore
from database import get_db

# ── concern → ingredient 키워드 매핑 (app.py 와 동일) ──────────────────────
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


def ingredient_concerns(name: str) -> list[str]:
    name_lower = name.lower()
    return [c for c, patterns in CONCERN_INGREDIENTS.items()
            if any(p in name_lower for p in patterns)]


def safe_doc_id(name: str) -> str:
    """성분 이름을 Firestore 문서 ID로 변환."""
    import re
    return re.sub(r'[^a-z0-9_]', '_', name.lower().strip())[:100]


def batch_set(db_fs, collection: str, docs: list[tuple], batch_size: int = 400):
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
        print(f"  [{collection}] committed {total}/{len(docs)}")


def main():
    key_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
    if not os.path.exists(key_path):
        print("ERROR: serviceAccountKey.json 파일을 찾을 수 없습니다.")
        print("Firebase Console > Project Settings > Service Accounts > Generate new private key")
        print("다운로드 후 이 스크립트와 같은 폴더에 serviceAccountKey.json 으로 저장하세요.")
        sys.exit(1)

    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)
    db_fs = firestore.client()

    conn = get_db()
    c    = conn.cursor()

    # ── 1. Ingredients ────────────────────────────────────────────────────
    print("\n=== [1/2] Ingredients 이관 중... ===")
    rows = c.execute("SELECT * FROM ingredients").fetchall()
    ing_sqlite_to_fsid: dict[int, str] = {}
    ing_docs = []

    for row in rows:
        r = dict(row)
        concerns = ingredient_concerns(r['name'])
        doc_id = safe_doc_id(r['name'])
        ing_sqlite_to_fsid[r['id']] = doc_id

        ing_docs.append((doc_id, {
            'name':        r['name'],
            'inci_name':   r.get('inci_name') or '',
            'ewg_score':   r.get('ewg_score'),
            'ewg_url':     r.get('ewg_url') or '',
            'function':    r.get('function') or '',
            'description': r.get('description') or '',
            'concerns':    concerns,
        }))

    batch_set(db_fs, 'ingredients', ing_docs)
    print(f"총 {len(ing_docs)}개 성분 완료.")

    # ── 2. Products ───────────────────────────────────────────────────────
    print("\n=== [2/2] Products 이관 중... ===")
    products = c.execute("SELECT * FROM products").fetchall()
    prod_docs = []

    for prod in products:
        p = dict(prod)
        pid = p['id']

        # 이 제품의 성분 목록 (순서 포함)
        ings = c.execute("""
            SELECT i.id, i.name, i.ewg_score, i.function, pi.position
            FROM product_ingredients pi
            JOIN ingredients i ON i.id = pi.ingredient_id
            WHERE pi.product_id = ?
            ORDER BY pi.position
        """, (pid,)).fetchall()

        ing_names    = [dict(i)['name']                        for i in ings]
        ing_doc_ids  = [ing_sqlite_to_fsid.get(dict(i)['id'], safe_doc_id(dict(i)['name'])) for i in ings]
        ing_ewg      = [dict(i)['ewg_score'] for i in ings]
        ing_func     = [dict(i)['function'] or '' for i in ings]
        ing_pos      = [dict(i)['position'] for i in ings]

        valid_scores = [s for s in ing_ewg if s is not None]
        avg_ewg      = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else None

        # 이 제품이 유발하는 피부/모발 concern 목록 (pre-compute)
        triggered: set[str] = set()
        for name in ing_names:
            triggered.update(ingredient_concerns(name))

        prod_docs.append((str(pid), {
            'name':               p['name'],
            'brand':              p.get('brand') or '',
            'category':           p.get('category') or '',
            'subcategory':        p.get('subcategory') or '',
            'price':              p.get('price') or 0,
            'retailer':           p.get('retailer') or '',
            'rating':             p.get('rating') or 0,
            'review_count':       p.get('review_count') or 0,
            'image_url':          p.get('image_url') or '',
            'product_url':        p.get('product_url') or '',
            'avg_ewg':            avg_ewg,
            'triggered_concerns': sorted(triggered),
            # 성분 목록 (modal 상세 표시용)
            'ingredient_names':   ing_names,
            'ingredient_doc_ids': ing_doc_ids,
            'ingredient_ewg':     ing_ewg,
            'ingredient_func':    ing_func,
            'ingredient_pos':     ing_pos,
        }))

    batch_set(db_fs, 'products', prod_docs)
    conn.close()

    print(f"\n✅ 완료! products {len(prod_docs)}개, ingredients {len(ing_docs)}개 Firestore에 업로드됨.")
    print("\n─── 다음 단계 ───────────────────────────────────────────")
    print("Firebase Console > Firestore Database > Rules 에 아래 규칙을 적용하세요:\n")
    print("""rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /products/{id}    { allow read: if true; allow write: if false; }
    match /ingredients/{id} { allow read: if true; allow write: if false; }
    match /users/{uid}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
  }
}""")


if __name__ == '__main__':
    main()
