# GlowCheck — Cosmetic Ingredient Transparency App

미국 화장품 성분 투명성 앱. 한국의 "화해"와 유사한 컨셉으로,
제품별 전성분을 EWG 안전도 기준으로 분석하고 피부 타입에 맞는 성분을 필터링할 수 있습니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 제품 검색 | 성분명·브랜드·제품명 통합 검색 |
| EWG 안전도 | 성분별 1(안전)~10(위험) 점수 표시 |
| 피부/모발 프로필 필터 | 건성·여드름·아토피·로제아 등 고민별 성분 자동 회피 |
| 제품 비교 | 최대 4개 제품 성분 나란히 비교 |
| 리뷰 | 로그인 후 별점·반응·텍스트 리뷰 작성 |
| Skin Diary | 피부 사진 업로드 → Gemini Vision AI 분석 → 날짜별 갤러리 + 2장 비교 |
| 인증 | Google OAuth + Email/Password (Firebase Auth) |

---

## 기술 스택

- **Backend**: Python 3.11 + Flask 3.0
- **Frontend**: Vanilla JS + Firebase JS SDK v10 (compat mode)
- **Database**: SQLite (로컬 개발) → Firebase Firestore (프로덕션)
- **인증**: Firebase Authentication
- **스토리지**: Firebase Storage (Skin Diary 사진, 제품 이미지)
- **AI 분석**: Google Gemini 1.5 Flash (텍스트 + Vision)
- **데이터 소스**: Open Beauty Facts API (600+ 제품)

---

## 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env` 파일 생성 (`.gitignore`에 포함됨 — 절대 커밋 금지):
```
GEMINI_API_KEY=your_gemini_api_key
```
Gemini API 키 발급: https://aistudio.google.com/app/apikey

### 3. Firebase 서비스 계정 키 설정
Firebase Console → 프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성
→ `serviceAccountKey.json`으로 저장 (`.gitignore`에 포함됨 — 절대 커밋 금지)

### 4. DB 초기화 + 샘플 데이터
```bash
python seed_data.py       # 기본 73개 제품 SQLite에 삽입
```

### 5. 서버 실행
```bash
python app.py
# 또는
python start.py
```
브라우저에서 `http://localhost:5000` 접속 (127.0.0.1 아님 — Firebase OAuth 오류 발생)

---

## 데이터 파이프라인

```
Open Beauty Facts API
        ↓
  expand_data.py          # 600+ 제품 SQLite 저장
        ↓
  firebase_migrate.py     # SQLite → Firestore 이관
        ↓  (--images 옵션 시)
  Firebase Storage         # 제품 이미지 업로드
```

### 순서대로 실행
```bash
python expand_data.py                    # Open Beauty Facts에서 600+ 제품 수집
python firebase_migrate.py               # Firestore 이관 (Firestore만)
python firebase_migrate.py --images      # Firestore 이관 + 이미지 Storage 업로드
```

> 이미 존재하는 제품은 (name, brand) 기준으로 중복 체크 후 스킵.
> `firebase_migrate.py`는 멱등성 보장 — 여러 번 실행해도 안전.

---

## 프로젝트 구조

```
glowcheck/
├── app.py                  Flask 백엔드 + /api/analyze-skin 엔드포인트
├── database.py             SQLite 스키마 정의 및 연결
├── seed_data.py            초기 73개 제품 샘플 데이터
├── expand_data.py          Open Beauty Facts API 대량 수집
├── firebase_migrate.py     SQLite → Firestore + Storage 이관
├── crawler.py              (레거시) 크롤러
├── requirements.txt
├── .env                    GEMINI_API_KEY (커밋 금지)
├── serviceAccountKey.json  Firebase 서비스 계정 키 (커밋 금지)
├── image/                  카테고리별 기본 제품 이미지 (fallback용)
│   ├── moisturizer.jpg
│   ├── serum.jpg
│   └── ...
├── data/
│   └── glowcheck.db        SQLite DB (자동 생성)
└── templates/
    └── index.html          SPA 프론트엔드 (전체 UI + Firebase SDK)
```

---

## Firebase 설정

**프로젝트**: `glowcheck-b8a8e`

**Firestore 보안 규칙**:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read: if true;
      allow write: if request.auth != null;
    }
  }
}
```

**Storage 보안 규칙**:
```
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /product_images/{allPaths=**} {
      allow read: if true;
      allow write: if request.auth != null;
    }
    match /skin_photos/{uid}/{allPaths=**} {
      allow read, write: if request.auth.uid == uid;
    }
  }
}
```

**필수 Firestore 복합 인덱스**:
- Collection: `reviews` / Fields: `product_id` (Asc) + `createdAt` (Desc)

---

## 보안 주의사항

- `serviceAccountKey.json` — 절대 git 커밋 금지
- `.env` — 절대 git 커밋 금지
- 두 파일 모두 `.gitignore`에 등록되어 있음
