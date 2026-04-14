# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

나라장터(G2B) AI 공고 추천 시스템의 백엔드 서비스 모음. 핵심 서비스는 `bid-sync/`로 통합되어 있으며, `logic/`은 Dify 워크플로우 코드 노드로 사용되는 독립 모듈들이다.

- **`bid-sync/`** — 공고 sync + HWP/HWPX→PDF 변환 통합 서비스 (포트 8000)
- **`logic/`** — Dify 코드 노드용 독립 Python 모듈
- **루트 `main.py`** — 구버전 변환 서비스 (bid-sync로 통합됨, 미사용)

---

## bid-sync 서비스

### 실행

```bash
cd bid-sync
# .env 설정 (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

```bash
# Docker
cd bid-sync
docker build -t bid-sync .
docker run -d --name bid-sync -p 8000:8000 --env-file .env bid-sync
```

### 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | `/bids/sync` | G2B API 직접 호출 후 bulk insert (body 없음) |
| POST | `/bids/process-files?limit=10` | PENDING 공고 RFP 변환 + Dify 업로드 |
| POST | `/bids/extract-keywords?limit=10` | DONE 공고 키워드 추출 + Dify 메타데이터 업데이트 |
| POST | `/convert` | URL의 HWP/HWPX/PDF → PDF 반환 |
| GET | `/health` | 헬스체크 |

---

## 전체 파이프라인 (아키텍처 문서: `doc/G2B_ai_recommend_archtect.md`)

```
Dify Schedule (10분)
  → POST /bids/sync           # G2B API items 저장
  → POST /bids/process-files      # PENDING 레코드 변환 + Dify 업로드
  → POST /bids/extract-keywords   # DONE 레코드 키워드 추출 + Dify 메타데이터 업데이트
```

### file_status 상태 전이
```
PENDING  ← RFP 파일 있는 공고 (sync 시점)
SKIPPED  ← RFP 없는 공고 (sync 시점)
DONE     ← 변환 + Dify 업로드 완료
FAILED   ← 변환 실패 (FILE_ERROR_MSG 기록)
```

---

## 코드 구조 (`bid-sync/`)

```
bid-sync/
├── main.py              # FastAPI 앱, 라우터 등록, 테이블 auto-create
├── database.py          # SQLAlchemy engine/session (.env 기반)
├── models.py            # Bid 모델 (tb_bids, 복합PK: bid_ntce_no + bid_ntce_ord)
├── schemas.py           # Pydantic 스키마
├── router/
│   ├── bids.py          # POST /bids/sync
│   ├── convert.py       # POST /convert
│   ├── process.py       # POST /bids/process-files
│   └── extract.py       # POST /bids/extract-keywords
└── services/
    ├── bid_classifier.py  # classify_bid() — 파일 분류, 취소/낙찰/유찰 스킵
    ├── converter.py       # LibreOffice 변환 로직 + prepare_pdf() (공통 유틸)
    ├── g2b_client.py      # fetch_bids() — G2B API 호출 + 페이징 (직전 10분 구간)
    ├── pdf_extractor.py   # extract_text() — pdfplumber 기반 PDF 텍스트 추출 (MAX_CHARS=8000)
    └── dify_client.py     # upload_to_knowledge(), run_keyword_workflow(), update_metadata()
```

### bid_classifier.py 핵심 로직
- `classify_bid(item)` → `None`(스킵 공고) 또는 `{has_rfp, rfp_url, file_urls, needs_llm, ...}`
- 파일명 키워드로 `rfp` / `exclude` / `unclear` 분류
- PDF 우선, 없으면 첫 번째 RFP 파일을 `rfp_url`로 선택

### converter.py 핵심 로직
- `validate_url()` — SSRF 방지, `ALLOWED_HOSTS = {"www.g2b.go.kr", "input.g2b.go.kr"}`
- `detect_file_info()` — content-type → content-disposition → URL path 순서로 파일 형식 판별
- `run_libreoffice()` — 요청별 독립 프로파일 디렉토리로 LibreOffice 병렬 실행 지원
- 스킵 대상이면 `None` 반환, 판별 불가면 400 에러

### /bids/sync 처리 흐름
1. `bidNtceNo` 없는 항목 필터
2. `tuple_().in_()` 으로 기존 공고 일괄 조회 (N+1 제거)
3. `classify_bid()` → 취소/낙찰/유찰이면 skip, 아니면 분류 결과로 Bid 생성
4. `bulk_save_objects()` + rollback 보장

---

## logic/ 모듈 (Dify 코드 노드)

각 파일이 `main()` 함수를 export하며 Dify 워크플로우에서 직접 호출됨.

- `logic/new/공고목록조회.py` — 나라장터 API 응답 파싱, 최신 차수 중복 제거, 파일 분류
- `logic/context_set.py` — Dify retrieval 결과를 LLM 프롬프트용 컨텍스트 문자열로 포맷

---

## 환경변수 (bid-sync/.env)

```
G2B_SERVICE_KEY    # 나라장터 API 서비스키
DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
DIFY_API_URL       # Dify 서버 base URL
DIFY_API_KEY       # 지식DB용 API 키 (dataset-...)
DIFY_DATASET_ID    # 공고 지식DB ID
DIFY_WORKFLOW_KEY  # 키워드 추출 워크플로우 API 키
```