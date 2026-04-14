# 나라장터 AI 공고 추천 시스템 아키텍처

> Claude Code 컨텍스트용 문서  
> 최종 정리: 2026-04-14

---

## 1. 전체 시스템 구조

### 기술 스택
| 레이어 | 기술               | 역할 |
|---|------------------|---|
| 스케줄러 | Dify 스케쥴 Node    | 10분 주기 G2B API 폴링 |
| API 서버 | FastAPI          | 파일 변환, DB 저장, Dify API 호출 |
| AI 추론 | Dify Workflow    | 키워드 추출, 추천 이유 생성 (LLM) |
| DB | MySQL (tb_bids)  | 공고 저장, 상태 관리 |
| 지식DB | Dify Knowledge   | RFP 문서 RAG (조건부 저장) |
| 파일변환 | FastAPI (별도 서비스) | HWP/HWPX → PDF |

### 역할 분리 원칙
```
FastAPI + Dify Schedule 담당:
  - G2B API 폴링 및 공고 수집
  - 파일 분류 (결정론적 키워드 매칭)
  - HWP → PDF 변환 API 호출
  - DB upsert / 상태 관리
  - Dify API 호출 (업로드, 키워드 추출 요청)

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

### 스킵 판단 흐름
```
Content-Type 확인
  → pdf / hwp 계열           → 처리
  → zip / rar 계열           → 스킵 (None 반환)

Content-Disposition filename 확인
  → SUPPORTED_SUFFIXES       → 처리
  → 그 외 확장자 있음         → 스킵 (None 반환)

URL path fallback
  → SUPPORTED_SUFFIXES       → 처리
  → 그 외                    → 스킵 (None 반환)

확장자도 Content-Type도 불명확 → 400 에러
```

### 스킵 응답 형식
```json
{ "skipped": true, "reason": "지원하지 않는 파일 형식", "url": "..." }
```

---

## 4. DB 스키마 (tb_bids)

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

-- 인덱스
create index idx_bids_bid_ntce_dt     on tb_bids (BID_NTCE_DT);
create index idx_bids_bid_clse_dt     on tb_bids (BID_CLSE_DT);
create index idx_bids_has_rfp         on tb_bids (HAS_RFP);
create index idx_bids_file_status     on tb_bids (FILE_STATUS);
create index idx_bids_keyword_status  on tb_bids (KEYWORD_STATUS);
create index idx_bids_ntce_instt      on tb_bids (NTCE_INSTT_NM);
create index idx_bids_clsfctn_no      on tb_bids (BID_CLSFCTN_NO);
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

---

## 5. SQLAlchemy Model

```python
from sqlalchemy import Column, String, DateTime, Text, Boolean, BigInteger, JSON, Index
from sqlalchemy.sql import func
from database import Base


class Bid(Base):
    __tablename__ = "tb_bids"

    bid_ntce_no          = Column(String(40),  primary_key=True, comment="공고번호")
    bid_ntce_ord         = Column(String(10),  primary_key=True, comment="공고차수")
    bid_ntce_nm          = Column(String(300), nullable=True,  comment="공고명")
    ntce_instt_cd        = Column(String(20),  nullable=True,  comment="공고기관코드")
    ntce_instt_nm        = Column(String(200), nullable=True,  comment="공고기관명")
    dmnd_instt_nm        = Column(String(200), nullable=True,  comment="수요기관명")
    bid_ntce_dt          = Column(String(20),  nullable=True,  comment="공고일시")
    bid_clse_dt          = Column(String(20),  nullable=True,  comment="입찰마감일시")
    openg_dt             = Column(String(20),  nullable=True,  comment="개찰일시")
    bid_mtd_nm           = Column(String(100), nullable=True,  comment="입찰방법")
    cntrct_cnclsn_mtd_nm = Column(String(100), nullable=True,  comment="계약방법")
    presmpt_prce         = Column(BigInteger,  nullable=True,  comment="추정가격(원)")
    bid_clsfctn_no       = Column(String(20),  nullable=True,  comment="입찰분류번호")

    has_rfp              = Column(Boolean,     default=False,  comment="RFP 포함 여부")
    rfp_file_url         = Column(Text,        nullable=True,  comment="RFP 파일 URL")
    file_urls            = Column(JSON,        nullable=True,  comment="첨부파일 URL 목록")
    file_status          = Column(String(20),  default="PENDING", nullable=True,
                                  comment="파일처리상태 PENDING/PROCESSING/DONE/FAILED/SKIPPED")
    file_processed_at    = Column(DateTime,    nullable=True,  comment="파일처리완료일시")
    file_error_msg       = Column(String(500), nullable=True,  comment="파일처리 실패사유")

    keywords             = Column(JSON,        nullable=True,  comment="추출 키워드 배열")
    keyword_status       = Column(String(20),  default="PENDING", nullable=True,
                                  comment="키워드추출상태 PENDING/DONE/FAILED")
    keyword_extracted_at = Column(DateTime,    nullable=True,  comment="키워드추출일시")
    dify_doc_id          = Column(String(100), nullable=True,  comment="Dify 지식DB 문서ID")

    raw_json             = Column(Text,        nullable=True,  comment="원본 JSON")
    created_at           = Column(DateTime, server_default=func.now())
    updated_at           = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_bids_bid_ntce_dt",    "bid_ntce_dt"),
        Index("idx_bids_bid_clse_dt",    "bid_clse_dt"),
        Index("idx_bids_has_rfp",        "has_rfp"),
        Index("idx_bids_file_status",    "file_status"),
        Index("idx_bids_keyword_status", "keyword_status"),
        Index("idx_bids_ntce_instt",     "ntce_instt_nm"),
        Index("idx_bids_clsfctn_no",     "bid_clsfctn_no"),
    )
```

---

## 6. 파일 분류 서비스 (bid_classifier.py)

```python
# services/bid_classifier.py

RFP_KEYWORDS = [
    "제안요청서", "rfp", "과업지시서", "과업내용서", "과업요청서",
    "규격서", "요구사항", "제안안내서", "사업수행계획",
    "기술규격", "과업범위", "업무범위", "기술제안", "수행계획",
    "사업내용", "과업설명서", "제안서작성", "기술사양"
]
EXCLUDE_KEYWORDS = ["입찰공고문", "유의사항", "계약서", "참가신청서", "서약서", "위임장"]
SKIP_NTCE_KIND   = {"취소공고", "낙찰공고", "유찰공고"}


def extract_files(item: dict) -> list[dict]:
    files = []
    for i in range(1, 11):
        suffix   = "" if i == 1 else str(i)
        name     = item.get(f"ntceSpecFileNm{suffix}", "").strip()
        file_url = item.get(f"ntceSpecDocUrl{suffix}", "").strip()
        if not name or not file_url:
            continue
        ext        = name.rsplit(".", 1)[-1].lower() if "." in name else "unknown"
        name_lower = name.lower()
        if any(kw in name_lower for kw in EXCLUDE_KEYWORDS):
            file_type = "exclude"
        elif any(kw in name_lower for kw in RFP_KEYWORDS):
            file_type = "rfp"
        else:
            file_type = "unclear"
        files.append({"index": i, "name": name, "url": file_url, "ext": ext, "file_type": file_type})
    return files


def pick_rfp_target(files: list[dict]) -> dict | None:
    """PDF 우선, 없으면 첫 번째 RFP 파일"""
    rfp_files = [f for f in files if f["file_type"] == "rfp"]
    return (
        next((f for f in rfp_files if f["ext"] == "pdf"), None)
        or (rfp_files[0] if rfp_files else None)
    )


def classify_bid(item: dict) -> dict | None:
    """스킵 대상이면 None 반환"""
    if item.get("ntceKindNm") in SKIP_NTCE_KIND:
        return None
    files  = extract_files(item)
    target = pick_rfp_target(files)
    unclear_files = [f for f in files if f["file_type"] == "unclear"]
    rfp_files     = [f for f in files if f["file_type"] == "rfp"]
    return {
        "has_rfp":    bool(target),
        "needs_llm":  len(unclear_files) > 0 and not rfp_files,
        "rfp_url":    target["url"]  if target else None,
        "rfp_name":   target["name"] if target else None,
        "rfp_ext":    target["ext"]  if target else None,
        "file_urls":  [f["url"] for f in files],
    }
```

---

## 7. Sync API (bids/sync)

### 핵심 개선 포인트
- **N+1 제거**: `tuple_().in_()` 으로 기존 공고 일괄 조회
- **bulk insert**: `db.bulk_save_objects()`
- **rollback 보장**: try/except로 감싸기
- **PRESMPT_PRCE**: 문자열 → int 변환 처리

```python
from sqlalchemy import tuple_

@router.post("/sync")
def sync_bids(req: BidSyncRequest, db: Session = Depends(get_db)):
    valid_items = [i for i in req.items if i.get("bidNtceNo")]
    skipped = len(req.items) - len(valid_items)

    # 기존 공고 일괄 조회
    keys = {(i["bidNtceNo"], i.get("bidNtceOrd", "00")) for i in valid_items}
    existing_keys = {
        (r.bid_ntce_no, r.bid_ntce_ord)
        for r in db.query(Bid.bid_ntce_no, Bid.bid_ntce_ord).filter(
            tuple_(Bid.bid_ntce_no, Bid.bid_ntce_ord).in_(keys)
        ).all()
    }

    new_bids = []
    for item in valid_items:
        key = (item["bidNtceNo"], item.get("bidNtceOrd", "00"))
        if key in existing_keys:
            skipped += 1
            continue

        classified = classify_bid(item)
        if classified is None:   # 취소/낙찰/유찰
            skipped += 1
            continue

        presmpt_prce = None
        try:
            raw = item.get("presmptPrce", "") or item.get("asignBdgtAmt", "")
            presmpt_prce = int(str(raw).replace(",", "")) if raw else None
        except (ValueError, TypeError):
            pass

        new_bids.append(Bid(
            bid_ntce_no          = item["bidNtceNo"],
            bid_ntce_ord         = item.get("bidNtceOrd", "00"),
            bid_ntce_nm          = item.get("bidNtceNm"),
            ntce_instt_cd        = item.get("ntceInsttCd"),
            ntce_instt_nm        = item.get("ntceInsttNm"),
            dmnd_instt_nm        = item.get("dmndInsttNm"),
            bid_ntce_dt          = item.get("bidNtceDt"),
            bid_clse_dt          = item.get("bidClseDt"),
            openg_dt             = item.get("opengDt"),
            bid_mtd_nm           = item.get("bidMtdNm"),
            cntrct_cnclsn_mtd_nm = item.get("cntrctCnclsnMtdNm"),
            presmpt_prce         = presmpt_prce,
            bid_clsfctn_no       = item.get("bidClsfctnNo"),
            has_rfp              = classified["has_rfp"],
            rfp_file_url         = classified["rfp_url"],
            file_urls            = classified["file_urls"],
            file_status          = "PENDING" if classified["has_rfp"] else "SKIPPED",
            keyword_status       = "PENDING",
            raw_json             = json.dumps(item, ensure_ascii=False),
        ))

    try:
        db.bulk_save_objects(new_bids)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"total": len(req.items), "inserted": len(new_bids), "skipped": skipped}
```

---

## 8. AI 추천 시스템

### 매칭 스코어 설계
```
최종 매칭 점수 =
  (품목코드 일치       × 0.35)   # 가장 신뢰도 높음
  + (키워드 임베딩 유사도 × 0.30)   # 의미 기반 매칭
  + (RFP RAG 매칭      × 0.25)   # 공고 상세 내용
  + (기업문서 분석      × 0.10)   # 홈페이지/업로드 자료
```

### 기업 정보 수집 우선순위
```
1순위: 사업자 정보 API → 업종코드, 세부품목코드
2순위: 업로드 문서 (회사소개서, 포트폴리오) → Dify 지식DB
3순위: 사업자등록증 OCR → 업태/종목 텍스트 추출
4순위: 홈페이지 URL → Jina AI Reader API 활용
        (https://r.jina.ai/{URL} 로 마크다운 변환)
```

### 추천 시점 전략 (1안 + 최적화 조합)
```
배치 수집 시점:
  → 활성 기업 기준: 최근 7일 로그인 OR 알림 수신 동의
  → 새 공고 매칭 즉시 실행 → 결과 RDB 캐싱

기업 메인 진입 시:
  → 캐시 결과 즉시 반환 (< 100ms)
  → 백그라운드 캐시 갱신 트리거
```

### 추천결과 캐시 테이블
```sql
company_recommendation (
    company_id      varchar(40),
    bid_ntce_no     varchar(40),
    bid_ntce_ord    varchar(10),
    match_score     float,
    match_keywords  json,
    ai_reason       text,
    generated_at    datetime,
    is_expired      tinyint(1),
    primary key (company_id, bid_ntce_no, bid_ntce_ord)
)
```

---

## 9. Dify 지식DB 저장 조건 (2단계 전략)

### 1단계 - 전체 공고 적용
- HWP → PDF 변환
- PDF 텍스트 추출 (pdfplumber / pymupdf)
- LLM 키워드 5~10개 추출 → `KEYWORDS` 컬럼 저장
- 1차 키워드 매칭 (빠름, 저비용)

### 2단계 - 조건부 Dify 저장
아래 조건 해당 시만 Dify 지식DB에 저장:
- 추정가격 1억원 이상
- IT/SW 관련 품목코드
- RFP 파일 존재하는 건

Dify 저장 후 `DIFY_DOC_ID` 기록 → 2차 정밀 RAG 매칭에 활용

---

## 10. Dify Metadata 필드 ID (현재 설정값)

```python
FIELD_IDS = {
    "bid_no":    "7bf5196d-2867-4b2e-ada3-41bb3ad852ed",
    "bid_ord":   "09860c77-a4d4-4255-852c-dbdbc889a622",
    "bid_kind":  "fd4d6ce3-1deb-48e9-9900-a9b4b1b9bdeb",
    "bid_title": "9b9ecfe1-59d3-401a-82db-78a10bdcc97f",
    "org_name":  "3a283e9f-eca2-4879-8069-c6a1abe152bb",
    "bid_date":  "d06d0d22-1678-4b28-8932-a1efccde3d7c",
    "open_date": "e7bf82d0-f23d-4e7d-87a0-73c6b8bdb40a",
    "budget":    "e543ca42-e956-4ea8-b973-448187a8f11f",
    "award_type":"cc43d5f2-8abb-48c8-8c86-fc05805831cb",
    "detail_url":"d40ef0a8-8144-40ca-851d-d8dc664fb47a",
}
```