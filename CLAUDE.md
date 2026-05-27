# CLAUDE.md — GlowCheck AI 협업 규칙

이 파일은 Claude Code가 매 세션 시작 시 자동으로 읽는 시스템 프롬프트입니다.
아래 규칙을 최우선으로 따르세요.

---

## 핵심 규칙

### 1. 코드 수정 전 반드시 확인
코드를 수정하기 전에 툴 실행 승인을 통해 사용자가 확인할 수 있도록 하세요.
대화로 "해도 될까요?"라고 묻지 않아도 됩니다 — 툴 실행 시 자동으로 Yes/No 버튼이 뜹니다.

### 2. 보안 절대 규칙
- `serviceAccountKey.json` — 절대 읽거나 출력하거나 커밋하지 말 것
- `.env` — 절대 읽거나 출력하거나 커밋하지 말 것
- 두 파일은 `.gitignore`에 등록되어 있으며 Firebase/Gemini 키를 포함함

### 3. 프로젝트 언어
- 코드 주석, 변수명: 영어
- 사용자와 대화: 한국어
- UI 텍스트: 영어 (현재 앱 기준)

### 4. 기술 스택 고수
- **프론트엔드**: Vanilla JS (React/Vue 도입 금지)
- **Firebase SDK**: compat mode (v10.12.2) — `firebase.firestore()` 방식
- **Python**: 3.11, Flask 3.0
- 새로운 의존성 추가 시 반드시 사용자에게 먼저 설명할 것

### 5. Firestore 비용 주의
- 클라이언트에서 전체 컬렉션 `.get()`은 localStorage 캐시 확인 후 실행
- 캐시 키: `gc_v3_products` (TTL 2h), `gc_v3_ingredients` (TTL 24h)
- 캐시 버전 변경 시 `CACHE_VER` 상수만 올리면 됨 (현재: `gc_v3`)
- 불필요한 실시간 리스너(`.onSnapshot`) 사용 금지

### 6. 데이터 파이프라인 순서
```
1. python expand_data.py          # Open Beauty Facts → SQLite
2. python firebase_migrate.py     # SQLite → Firestore
3. (선택) python firebase_migrate.py --images  # 이미지 → Storage
```
migrate 실행 후 브라우저에서 `cacheClear()` 또는 CACHE_VER 버전 업 필요

---

## 프로젝트 핵심 컨텍스트

### Firebase 프로젝트
- Project ID: `glowcheck-b8a8e`
- Storage Bucket: `glowcheck-b8a8e.firebasestorage.app`
- Auth Domain: `glowcheck-b8a8e.firebaseapp.com`
- 로컬 접속: `http://localhost:5000` (127.0.0.1 사용 시 OAuth 오류)

### Firestore 컬렉션 구조 (플랫)
| 컬렉션 | 문서 ID | 설명 |
|--------|---------|------|
| `products/{id}` | SQLite id | 제품 전체 정보 + 성분 배열 인라인 |
| `brands/{slug}` | safe_slug(brand) | 브랜드 메타 |
| `ingredients/{slug}` | safe_slug(name) | 성분 정보 + concerns 배열 |
| `reviews/{id}` | auto | 리뷰 (product_id, userId, rating, ...) |
| `users/{uid}` | Firebase UID | 프로필, avatarUrl, skinProfile, lastLoginAt |
| `users/{uid}/skin_logs/{id}` | auto | Skin Diary 항목 + AI 분석 결과 |
| `users/{uid}/reviews/{id}` | auto | 유저별 리뷰 사본 (dual write) |

### 피부 고민 → 회피 성분 매핑
`CONCERN_INGREDIENTS` 딕셔너리가 `app.py`와 `firebase_migrate.py` 양쪽에 동일하게 존재.
수정 시 두 파일 모두 업데이트 필요.

### 이미지 Fallback 우선순위
1. `p.image_url` (Firestore 저장값, Open Beauty Facts URL)
2. `productFallbackImg(p)` — 카테고리별 `/image/*.jpg` 로컬 이미지

### 인증 플로우
1. Google OAuth 또는 Email/Password 로그인
2. 로그인 성공 → `ensureUserProfile(user)` 호출
3. `avatarUrl` 없으면 `pickAvatar(uid)` (uid 합산 % 11 → `/image/` 폴더 중 하나)
4. `lastLoginAt` Firestore에 기록

---

## 자주 발생하는 이슈

| 이슈 | 원인 | 해결 |
|------|------|------|
| 제품이 73개만 로딩 | localStorage 캐시 만료 전 stale data | `CACHE_VER` 올리기 또는 `cacheClear()` |
| Firestore index error (reviews) | 복합 인덱스 미생성 | Firebase Console → Indexes → reviews(product_id Asc, createdAt Desc) |
| safe_slug 오류 "reserved id" | 특수문자만 있는 성분명 | `safe_slug(name, fallback_id=id)` 사용 |
| OAuth 오류 | 127.0.0.1으로 접속 | localhost:5000 으로 접속 |
| 이미지 안 보임 | seed 제품 image_url=null | category fallback 이미지 자동 표시됨 |

---

## 파일별 역할 요약

| 파일 | 역할 |
|------|------|
| `templates/index.html` | 전체 SPA UI + Firebase SDK + 모든 JS 로직 |
| `app.py` | Flask 라우트, `/api/analyze-skin` (Gemini Vision), `/image/<file>` |
| `database.py` | SQLite 스키마 (products, ingredients, product_ingredients, crawl_log) |
| `expand_data.py` | Open Beauty Facts API → SQLite 대량 수집 |
| `firebase_migrate.py` | SQLite → Firestore + (--images) Storage |
| `seed_data.py` | 초기 73개 샘플 제품 데이터 |
| `crawler.py` | 레거시 크롤러 (현재 미사용) |
