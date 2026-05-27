# ARCHITECTURE.md — GlowCheck 시스템 설계

AI 에이전트가 코딩 작업 전 전체 구조를 파악하기 위한 문서입니다.

---

## 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────┐
│                        브라우저 (SPA)                        │
│  templates/index.html                                        │
│  ├── Firebase JS SDK v10 (compat)                           │
│  │   ├── Firebase Auth  (Google OAuth / Email+Password)     │
│  │   ├── Firestore      (제품·성분·리뷰 읽기)               │
│  │   └── Storage        (Skin Diary 사진 업로드)            │
│  └── Vanilla JS                                             │
│      ├── localStorage 캐시 (TTL: 2h products, 24h ings)    │
│      └── fetch → Flask API (/api/analyze-skin 등)          │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP (localhost:5000)
┌─────────────────────▼───────────────────────────────────────┐
│                   Flask Backend (app.py)                     │
│  ├── GET  /                  → index.html 렌더링            │
│  ├── GET  /image/<file>      → /image/ 폴더 정적 파일       │
│  └── POST /api/analyze-skin  → Gemini Vision AI 분석        │
└─────────────────────┬───────────────────────────────────────┘
                      │
         ┌────────────▼────────────┐
         │   Google Gemini API     │
         │   (gemini-1.5-flash)    │
         │   Vision + Text         │
         └─────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Firebase (Google Cloud)                     │
│  ├── Firestore (NoSQL)                                      │
│  │   ├── /products/{id}                                     │
│  │   ├── /brands/{slug}                                     │
│  │   ├── /ingredients/{slug}                                │
│  │   ├── /reviews/{id}                                      │
│  │   └── /users/{uid}/...                                   │
│  ├── Authentication                                         │
│  └── Storage                                                │
│      ├── product_images/{productId}.jpg                     │
│      └── skin_photos/{uid}/{filename}                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 데이터 레이어

### SQLite (로컬 개발용)
파일: `data/glowcheck.db`

```
products
  id, name, brand, category, subcategory,
  price, currency, image_url, product_url,
  retailer, rating, review_count, created_at

ingredients
  id, name, inci_name, ewg_score, ewg_url,
  function, description, concerns, skin_types, created_at

product_ingredients  (다대다 연결)
  product_id, ingredient_id, position

crawl_log
  id, source, status, records, crawled_at
```

### Firestore (프로덕션)
플랫(flat) 컬렉션 구조 — 계층 구조 없이 모두 최상위 컬렉션.

```
products/{productId}
  id, name, brand, brand_slug, category, subcategory,
  price, retailer, rating, review_count, avg_rating,
  image_url, product_url, avg_ewg, triggered_concerns[],
  ingredient_names[], ingredient_doc_ids[], ingredient_ewg[],
  ingredient_func[], ingredient_pos[]

brands/{brandSlug}
  name, slug, categories[], product_count

ingredients/{slug}
  name, inci_name, ewg_score, ewg_url,
  function, description, concerns[]

reviews/{reviewId}
  product_id, userId, displayName, avatarUrl,
  rating, reaction, text, createdAt

users/{uid}
  displayName, email, avatarUrl, role, lastLoginAt,
  skinProfile: { skinType, concerns[], ageRange, hairConcerns[] }

users/{uid}/skin_logs/{logId}
  photoURL, storagePath, note, createdAt,
  analysisStatus, analysis: { score, summary, hydration,
    redness, texture, pores, concerns[], positives[], recommendations[] }

users/{uid}/reviews/{reviewId}
  (reviews 컬렉션과 동일 — 유저별 조회를 위한 dual write)
```

---

## 프론트엔드 상태 관리

SPA이지만 프레임워크 없음. 전역 변수로 상태 관리.

```javascript
// 인메모리 캐시 (Firestore 읽기 최소화)
let _allProducts    = null   // 전체 제품 배열 (캐시됨)
let _allIngredients = null   // 전체 성분 배열 (캐시됨)
let _allBrands      = null   // 전체 브랜드 배열 (캐시됨)

// localStorage 캐시 키 (버전: gc_v3)
// gc_v3_products   → { products[], brands[] }  TTL 2h
// gc_v3_ingredients → ingredients[]             TTL 24h

// 필터 상태
let state = {
  tab, q, category, retailer, sort, page,
  minPrice, maxPrice,
  ewgSafe, ewgModerate, ewgHazard,
  avoidConcerns[],    // 피부/모발 고민 필터
  avoidIngredients[], // 직접 입력 회피 성분
}

// 제품 비교
let compareSet = new Map()  // id → product object (최대 4개)

// 현재 열린 제품 모달
let currentProductId = null
```

---

## 핵심 데이터 흐름

### 제품 목록 로딩
```
페이지 로드
  → DOMContentLoaded → loadProducts()
  → ensureDataLoaded()
      → cacheGet('products') 확인
      → 캐시 있으면: 인메모리에 할당 (Firestore 읽기 0)
      → 캐시 없으면: Firestore products + brands 병렬 조회
                    → cacheSet('products', data, 2h)
  → 클라이언트 사이드 필터링 (검색·카테고리·EWG·가격·concerns)
  → 페이지네이션 (24개씩)
  → productCard(p) HTML 생성 → main-content 삽입
```

### Skin Diary 업로드 흐름
```
사진 선택 (file input)
  → handleSkinUpload(event)
  → Firebase Storage 업로드 (skin_photos/{uid}/{timestamp}.jpg)
    → 업로드 진행률 표시
  → Firestore users/{uid}/skin_logs 문서 생성 (analysisStatus: 'pending')
  → POST /api/analyze-skin { photoURL, logId, uid }
      → Flask: Storage URL에서 이미지 다운로드
      → PIL.Image로 열기
      → Gemini 1.5 Flash Vision API 호출
      → JSON 파싱 (score, summary, hydration, redness, ...)
      → return { analysis }
  → Firestore skin_log 문서 업데이트 (analysisStatus: 'done', analysis: {...})
  → UI 갤러리 갱신
```

### 리뷰 작성 흐름
```
submitReview()
  → Firestore에 dual write:
      1. reviews/{auto} 생성       (제품별 조회용)
      2. users/{uid}/reviews/{auto} (유저별 조회용)
  → loadProductReviews(productId) 재호출
  → reviews 컬렉션 쿼리: product_id == ? ORDER BY createdAt DESC
    (복합 인덱스 필요: product_id Asc + createdAt Desc)
```

---

## API 엔드포인트 (Flask)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | index.html SPA 렌더링 |
| GET | `/image/<filename>` | /image/ 폴더 정적 파일 서빙 |
| POST | `/api/analyze-skin` | Gemini Vision 피부 분석 |
| POST | `/api/crawl` | (레거시) 크롤러 수동 실행 |

> 대부분의 데이터 조회는 클라이언트가 Firestore SDK로 직접 처리.
> Flask는 Gemini AI 호출처럼 서버 사이드가 필요한 작업만 담당.

---

## 인증 흐름

```
signInWithGoogle() 또는 signInWithEmail()
  → Firebase Auth 처리
  → onAuthStateChanged 콜백
      → ensureUserProfile(user)
          → users/{uid} 문서 조회
          → 없으면 신규 생성 (displayName, email, avatarUrl, role:'user')
          → avatarUrl: photoURL || pickAvatar(uid)
            (uid 문자 합산 % 11 → /image/ 중 하나 고정 배정)
          → lastLoginAt: serverTimestamp() 업데이트
      → UI 업데이트 (아바타, 이름 표시)
```

---

## 성분 안전도 분석

### EWG 점수 (Firestore 저장)
- 1~2: 안전 (green)
- 3~6: 보통 (orange)
- 7~10: 위험 (red)
- 제품 `avg_ewg` = 유효 성분 점수 평균

### 피부 고민 → 회피 성분 매핑 (`CONCERN_INGREDIENTS`)
`app.py`와 `firebase_migrate.py` 두 곳에 동일하게 정의됨.

```python
{
  'dry_skin':        ['alcohol denat', 'sodium lauryl sulfate', ...],
  'acne_prone':      ['coconut oil', 'mineral oil', ...],
  'eczema_atopic':   ['fragrance', 'parfum', 'methylisothiazolinone', ...],
  'rosacea':         ['witch hazel', 'menthol', 'fragrance', ...],
  'sun_sensitive':   ['glycolic acid', 'retinol', ...],
  'acid_sensitive':  ['glycolic acid', 'lactic acid', 'salicylic acid', ...],
  'fine_hair':       ['dimethicone', 'mineral oil', ...],
  'hair_loss':       ['sodium lauryl sulfate', 'ammonium lauryl sulfate', ...],
  'scalp_sensitive': ['fragrance', 'methylisothiazolinone', ...],
  'curly_hair':      ['sodium lauryl sulfate', 'isopropyl alcohol', ...],
}
```

---

## 확장 포인트 (향후 개발 참고)

| 영역 | 현재 | 확장 방향 |
|------|------|-----------|
| 데이터 | 664개 제품 (OBF) | 크롤러 고도화, 더 많은 소스 |
| 검색 | 클라이언트 문자열 매칭 | Firestore full-text 또는 Algolia |
| AI 분석 | Gemini Vision (피부 사진) | 성분 AI 설명, 개인화 추천 |
| 인증 | Google + Email/Password | Apple, Kakao 등 추가 가능 |
| 가격 | 정적 DB 데이터 | 실시간 크롤링 연동 |
| 알림 | 없음 | 관심 성분 신제품 푸시 알림 |
