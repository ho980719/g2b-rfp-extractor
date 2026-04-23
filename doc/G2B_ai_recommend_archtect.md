# 나라장터 AI 공고 추천 시스템 아키텍처

> 최종 정리: 2026-04-21

---

## 1. 전체 시스템 구조

### 기술 스택
| 레이어 | 기술 | 역할 |
|---|---|---|
| 스케줄러 | Dify 스케쥴 Node | 10분 주기 G2B API 폴링 |
| API 서버 | FastAPI | 파일 변환, DB 저장, Dify API 호출 |
| AI 추론 | Dify Workflow | 키워드 추출, 추천 이유 생성 (LLM) |
| DB | MySQL (tb_bids, tb_bids_company_mapping) | 공고 저장, 매칭 결과 저장 |
| 지식DB | Dify Knowledge | RFP 문서 RAG (조건부 저장) |
| 파일변환 | FastAPI (별도 서비스) | HWP/HWPX → PDF |

### 역할 분리 원칙
```
FastAPI + Dify Schedule 담당:
  - G2B API 폴링 및 공고 수집
  - 파일 분류 (결정론적 키워드 매칭)
  - HWP → PDF 변환 API 호출
  - DB upsert / 상태 관리
  - Dify API 호출 (업로드, 키워드 추출 요청)
  - 기업-공고 매칭 (품목코드 + 키워드 + RAG)

Dify 담당 (LLM 추론만):
  - unclear 파일 RFP 여부 판단
  - 키워드 추출 Workflow
  - 기업-공고 매칭 추천 이유 생성 Workflow
```

---

## 2. 공고 Sync 전체 플로우

```
[Dify Schedule - 10분 주기]
        │
        ▼
  G2B API 호출 (startDt ~ endDt)
        │
        ▼
  파일 분류 (bid_classifier.py)
        │
        ├─ 취소/낙찰/유찰 공고 → 스킵
        │
        ▼
  DB upsert (tb_bids)
  - has_rfp, rfp_file_url, file_urls 저장
  - srvce_div_nm, is_mock_yn, is_urgent_yn 저장
  - file_status = PENDING (RFP 있을 때)
  - file_status = SKIPPED (RFP 없을 때)
  - keyword_status = PENDING
        │
        ▼
  [Task - RFP 파일 처리]
        │
        ├─ HWP/HWPX → convert API 호출 → PDF
        ├─ Dify 지식DB 업로드 (조건부*)
        └─ file_status = DONE / FAILED 업데이트
        │
        ▼
  [Task - 키워드 추출]
        │
        ├─ Dify Workflow API 호출
        │    입력: bid_title + rfp_text
        │    출력: keywords[]
        └─ keyword_status = DONE 업데이트
        │
        ▼
  [Task - 공고 매칭]
  POST /matching/run
        │
        └─ 활성 기업 순회 → match_company()
             - 품목코드 + 키워드 필터 → 후보 추출
             - Dify RAG 점수 조회
             - 최종 점수 계산 → tb_bids_company_mapping upsert
             - 점수 < 0.40 → 저장 제외
        │
        ▼
  [Task - 추천 이유 생성]
  POST /matching/generate-reasons
        │
        └─ reason_status=PENDING 매핑 순회
             - Dify 추천이유 워크플로우 호출
             - match_reason 업데이트
             - reason_status = DONE / FAILED

  * Dify 공고 지식DB 조건부 저장 기준:
    - RFP 파일 존재하는 건
```

---

## 3. HWP → PDF 변환 서비스

### 엔드포인트
```
POST /convert
Body: { "url": "https://..." }
Response: PDF 파일 (FileResponse)

GET /health
```

### 핵심 구현 포인트
- `asyncio.create_subprocess_exec` 사용 (blocking 방지)
- LibreOffice 요청별 독립 프로파일 디렉토리 (`--env:UserInstallation=file://...`)
- 변환 타임아웃: 60초
- 파일 크기 제한: 50MB
- SSRF 방지: 허용 도메인 화이트리스트 (`ALLOWED_HOSTS`)

### 지원/스킵 파일 형식
```python
SUPPORTED_SUFFIXES = {".pdf", ".hwp", ".hwpx"}

SKIP_SUFFIXES = {
    ".zip", ".alz", ".rar", ".7z", ".tar", ".gz",   # 압축
    ".xls", ".xlsx", ".doc", ".docx", ".ppt", ".pptx",  # 오피스
    ".txt", ".csv", ".xml", ".json",                  # 텍스트
    ".jpg", ".jpeg", ".png", ".gif",                  # 이미지
}
```

---

## 4. DB 스키마

### tb_bids
```sql
create table tb_bids
(
    -- 기본 식별자
    BID_NTCE_NO          varchar(40)   not null comment '공고번호',
    BID_NTCE_ORD         varchar(10)   not null comment '공고차수',

    -- 공고 기본 정보
    BID_NTCE_NM          varchar(300)  null comment '공고명',
    NTCE_INSTT_CD        varchar(20)   null comment '공고기관코드',
    NTCE_INSTT_NM        varchar(200)  null comment '공고기관명',
    DMND_INSTT_NM        varchar(200)  null comment '수요기관명',
    BID_NTCE_DT          varchar(20)   null comment '공고일시',
    BID_CLSE_DT          varchar(20)   null comment '입찰마감일시',
    OPENG_DT             varchar(20)   null comment '개찰일시',
    BID_MTD_NM           varchar(100)  null comment '입찰방법',
    CNTRCT_CNCLSN_MTD_NM varchar(100)  null comment '계약방법',
    PRESMPT_PRCE         bigint        null comment '추정가격(원)',
    BID_CLSFCTN_NO       varchar(20)   null comment '입찰분류번호(품목코드)',
    BID_KIND             varchar(100)  null comment '공고종류',
    SRVCE_DIV_NM         varchar(100)  null comment '서비스구분명 (기술용역 등)',
    IS_MOCK_YN           varchar(1)    default 'N' comment '모의공고여부 (공고번호 T로 시작 시 Y)',
    IS_URGENT_YN         varchar(1)    default 'N' comment '긴급공고여부 (ntceKindNm 긴급 포함 시 Y)',
    DETAIL_URL           text          null comment '공고 상세링크',

    -- RFP 파일 처리
    HAS_RFP              tinyint(1)    default 0    null comment 'RFP 포함 여부',
    RFP_FILE_URL         text          null comment 'RFP 파일 URL (대표 1개)',
    FILE_URLS            json          null comment '전체 첨부파일 URL 목록',
    FILE_STATUS          varchar(20)   default 'PENDING' null
                         comment '파일처리상태: PENDING/PROCESSING/DONE/FAILED/SKIPPED',
    FILE_PROCESSED_AT    datetime      null comment '파일처리 완료일시',
    FILE_ERROR_MSG       varchar(500)  null comment '파일처리 실패사유',

    -- AI 추천 관련
    KEYWORDS             json          null comment '추출 키워드 배열',
    KEYWORD_STATUS       varchar(20)   default 'PENDING' null
                         comment '키워드추출상태: PENDING/DONE/FAILED',
    KEYWORD_EXTRACTED_AT datetime      null comment '키워드추출 완료일시',
    DIFY_DOC_ID          varchar(100)  null comment 'Dify 지식DB 문서ID',

    -- 메타
    RAW_JSON             longtext      null comment '원본 JSON',
    CREATED_AT           datetime      default CURRENT_TIMESTAMP null,
    UPDATED_AT           datetime      default CURRENT_TIMESTAMP null
                         on update CURRENT_TIMESTAMP,

    primary key (BID_NTCE_NO, BID_NTCE_ORD)
) comment '나라장터 입찰공고' collate = utf8mb4_unicode_ci;
```

### file_status 상태 전이
```
PENDING
  → (RFP 없음)    → SKIPPED
  → (변환 실패)   → FAILED   (FILE_ERROR_MSG 기록)
  → (변환 성공)   → DONE     (FILE_PROCESSED_AT 기록)
                       ↓
                 조건 충족 시 Dify 업로드
                       ↓
                 DIFY_DOC_ID 기록
```

### tb_bids_company_mapping
```sql
create table tb_bids_company_mapping
(
    COMPANY_ID      bigint          not null comment '기업ID',
    BID_NTCE_NO     varchar(40)     not null comment '공고번호',
    BID_NTCE_ORD    varchar(10)     not null comment '공고차수',
    MATCH_TYPE_CD   varchar(20)     default 'AI'      comment '매칭유형 (AI/MANUAL)',
    MATCH_SCORE     decimal(5,4)    null               comment '매칭점수 (0.0000~1.0000)',
    MATCH_REASON    varchar(1000)   null               comment '매칭사유 (AI 생성 추천 이유)',
    MATCH_KEYWORDS  json            null               comment '매칭 근거 JSON',
    REASON_STATUS   varchar(20)     default 'PENDING'  comment '추천이유 생성상태 PENDING/DONE/FAILED',
    BOOKMARK_YN     varchar(1)      default 'N'        comment '북마크 여부',
    LAST_MATCH_DT   datetime        null               comment '마지막 매칭일시',
    CREATED_AT      datetime        default CURRENT_TIMESTAMP,
    UPDATED_AT      datetime        null on update CURRENT_TIMESTAMP,
    primary key (COMPANY_ID, BID_NTCE_NO, BID_NTCE_ORD)
) comment '기업-공고 매칭 결과';
```

#### MATCH_KEYWORDS JSON 구조
```json
{
  "items":      ["8111159901"],
  "item_names": ["정보시스템개발서비스"],
  "keywords":   ["정보시스템개발서비스", "AI 챗봇"],
  "rag": {
    "score":   0.4285,
    "segment": "RFP 본문 유사 조각 (최대 200자)"
  }
}
```
- `items`: 매칭된 세부품목 코드
- `item_names`: 매칭된 세부품목명
- `keywords`: 프론트 표시용 (item_names + 키워드 매칭 합산)
- `rag`: Dify 시맨틱 검색 결과 (dify_doc_id 있는 공고만)

---

## 5. AI 매칭 시스템

### 매칭 스코어 설계
```
최종 매칭 점수 = (합계 최대 1.0)
  품목코드 일치   × 0.40   # 가장 신뢰도 높음 (세부품목 전방일치)
  키워드 매칭     × 0.35   # 기업 등록 키워드 (alias 포함) vs 공고 추출 키워드
  RFP RAG 매칭   × 0.25   # Dify 시맨틱 유사도 (RFP 있는 공고만)

* 점수 0.40 미만은 저장 제외
* RAG 리스케일: (raw_score - 0.2) / 0.4 → 0.0~1.0
```

### 매칭 파이프라인
```
1단계: DB 필터
  - 기업 품목코드 전방일치 OR 기업 키워드 포함 매칭
  - 예산 범위 필터 (budget_min / budget_max)
  - 마감일 지난 공고 제외

2단계: RAG 점수 조회
  - 후보 공고의 dify_doc_id 대상 Dify retrieve API 호출
  - 기업 프로필 요약 + 키워드 쿼리로 시맨틱 검색
  - 문서당 최고 점수 세그먼트 저장

3단계: 점수 계산 + upsert
  - 점수 < 0.40 → 저장 제외 (기존 레코드 있으면 삭제)
  - reason_status = PENDING으로 저장
```

### 매칭 엔드포인트
| Method | Path | 설명 |
|--------|------|------|
| POST | `/matching/run` | 활성 기업 전체 배치 매칭 (new_only=True) |
| POST | `/matching/run/{company_id}` | 특정 기업 전체 재매칭 (프로필 변경 시) |
| POST | `/matching/generate-reasons?limit=20` | PENDING 매핑 추천 이유 생성 |
| POST | `/matching/refresh-keywords` | 기존 매핑 match_keywords 재생성 (교정용) |

### 스케쥴링 체인
```
POST /bids/sync
  → POST /bids/process-files?limit=50
    → POST /bids/extract-keywords?limit=50
      → POST /matching/run
        → POST /matching/generate-reasons?limit=50
```

---

## 6. 파일 분류 서비스 (bid_classifier.py)

```python
RFP_KEYWORDS = [
    "제안요청서", "rfp", "과업지시서", "과업내용서", "과업요청서",
    "규격서", "요구사항", "제안안내서", "사업수행계획",
    "기술규격", "과업범위", "업무범위", "기술제안", "수행계획",
    "사업내용", "과업설명서", "제안서작성", "기술사양"
]
EXCLUDE_KEYWORDS = ["입찰공고문", "유의사항", "계약서", "참가신청서", "서약서", "위임장"]
SKIP_NTCE_KIND   = {"취소공고", "낙찰공고", "유찰공고"}
```

---

## 7. Sync API (bids/sync)

### 핵심 구현 포인트
- **N+1 제거**: `tuple_().in_()` 으로 기존 공고 일괄 조회
- **bulk insert**: `db.bulk_save_objects()`
- **rollback 보장**: try/except로 감싸기
- **PRESMPT_PRCE**: 문자열 → int 변환 처리
- **pubPrcrmntClsfcNo 우선**: `item.get("pubPrcrmntClsfcNo") or item.get("bidClsfctnNo")`

---

## 8. Dify 연동

### 워크플로우 목록
| 키 | 용도 | 입력 | 출력 |
|---|---|---|---|
| `DIFY_WORKFLOW_KEY` | 키워드 추출 | bid_title, rfp_text | keywords[] |
| `DIFY_REASON_WORKFLOW_KEY` | 추천 이유 생성 | bid_title, bid_agency, bid_amount, service_type, matched_items, matched_keywords, rag_segment, match_score | reason |

### 추천 이유 워크플로우 프롬프트 규칙
```
- "고객님이 등록한" 으로 시작
- 세부품목만 있으면: "{품목명} 세부품목이..."
- 키워드만 있으면: "{키워드명} 키워드가..."
- 둘 다 있으면: 세부품목 및 키워드 함께 언급
- 빈 값 항목은 절대 언급하지 말 것
- 한 문장만 출력
```

### Dify Metadata 필드 ID
```python
FIELD_IDS = {
    "bid_no":         "efda07c9-ee86-4f04-b32e-9d4abf7d6a4d",
    "bid_ord":        "35af4325-21ec-4f17-a635-1a69e490c777",
    "bid_kind":       "de6131bb-ce81-4c05-9fab-aba4e886d268",
    "bid_title":      "8f36b8be-3774-4aa5-b5af-b856f96b5f48",
    "org_name":       "2c31b48c-2d45-452e-8c35-9a506dc038f8",
    "bid_date":       "397d393f-aa99-4c5e-b959-5922ee8ee79c",
    "open_date":      "16e08ac3-7c34-46f5-99ee-f6147b70a156",
    "budget":         "9afde289-caee-4843-a4fe-92707b033d8b",
    "award_type":     "8208c990-ee05-461a-9449-406aa969fc2c",
    "detail_url":     "3fbf2de6-b71e-4214-89ec-ddb94dd9c708",
    "bid_clse_dt":    "e277352e-4672-45b5-b3bb-fd1d38937f5b",
    "keywords":       "7bf6efcb-9aac-4914-9a4e-bcef863ecf41",
    "bid_clsfctn_no": "42ffdf20-443c-4455-850e-9093b6b1279c",
}
```

---

## 9. 구독 플랜 사용량 제한

### 개요
매칭 시 기업의 활성 구독 플랜을 확인하여 일별 추천 건수를 제한한다.
구독이 없거나 ACTIVE 상태가 아니면 매칭을 스킵한다.

### Python 배치 담당 기능
| FEATURE_TYPE | 체크 시점 | Free | Pro | Business | Enterprise |
|---|---|---|---|---|---|
| `BID_RECOMMEND` | 공고 매칭 저장 직전 | 15건/일 | 15건/일 | 25건/일 | 무제한 |
| `PRESPEC_RECOMMEND` | 사전규격 매칭 시 | 5건/일 | 5건/일 | 5건/일 | 무제한 |
| `ALARM_KAKAO` | 카카오 알림 발송 직전 | 1건/일 | 10건/일 | 20건/일 | 무제한 |

> `NULL = 무제한` / Java 앱 담당: `AI_SUMMARY`, `AI_SEARCH`

### 관련 테이블
```
tb_subscription (COMPANY_ID, PLAN_ID, STATUS)
  └─ tb_subscription_plan (BID_RECOMMEND_DAY_LIMIT, ...)
tb_subscription_usage_daily (COMPANY_ID, FEATURE_TYPE, USE_DT, USE_COUNT)
  PK: (COMPANY_ID, FEATURE_TYPE, USE_DT)  ← 날짜별 자동 분리, 리셋 배치 불필요
```

### match_company() 처리 흐름
```
1. get_plan_limits(company_id)
   → None이면 "no_subscription" 스킵
   → BID_RECOMMEND_DAY_LIMIT 확인

2. get_today_usage(company_id, "BID_RECOMMEND")
   → 이미 한도 초과 시 "limit_exceeded" 스킵

3. 매칭 루프
   → 신규 저장 시: today_usage + new_count >= limit 이면 continue
   → 기존 매핑 업데이트는 카운트 차감 없음

4. increment_usage(company_id, "BID_RECOMMEND", new_count)
   → 신규 추천 건수만큼 한 번에 upsert
```

### 구현 파일
`bid-sync/services/usage_limiter.py`
- `get_plan_limits(company_id, db) → dict | None`
- `get_today_usage(company_id, feature_type, db) → int`
- `increment_usage(company_id, feature_type, amount, db)`

---

## 10. 환경변수 (.env)

```
G2B_SERVICE_KEY          # 나라장터 API 서비스키

DB_HOST
DB_PORT
DB_USER
DB_PASSWORD
DB_NAME

DIFY_API_URL             # Dify 서버 base URL
DIFY_API_KEY             # 지식DB용 API 키 (dataset-...)
DIFY_DATASET_ID          # 공고 지식DB ID
DIFY_WORKFLOW_KEY        # 키워드 추출 워크플로우 API 키
DIFY_REASON_WORKFLOW_KEY # 추천 이유 생성 워크플로우 API 키

LOG_LEVEL                # 로그 레벨 (기본 INFO)
```

---

## 10. Dify 지식DB 저장 조건 (2단계 전략)

### 1단계 - 전체 공고 적용
- HWP → PDF 변환
- PDF 텍스트 추출 (PyMuPDF)
- LLM 키워드 5~10개 추출 → `KEYWORDS` 컬럼 저장
- 1차 키워드 매칭 (빠름, 저비용)

### 2단계 - 조건부 Dify 저장
아래 조건 해당 시만 Dify 지식DB에 저장:
- RFP 파일 존재하는 건

Dify 저장 후 `DIFY_DOC_ID` 기록 → 2차 정밀 RAG 매칭에 활용