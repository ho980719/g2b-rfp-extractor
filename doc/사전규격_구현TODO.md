# 사전규격 공고 매칭 서비스 — 구현 TODO

> 작성일: 2026-04-24  
> 참고: `doc/개발현황.md` (기존 입찰공고 파이프라인)

---

## UI 요구 필드 (사전규격LIST.png 기준)

| UI 항목 | 매핑 컬럼 |
|---|---|
| 공고명 | `prdct_clsfc_no_nm` |
| 마감일 / D-day | `opnin_rgst_clse_dt` |
| 발주기관 태그 | `order_instt_nm` |
| 예산 태그 | `asign_bdgt_amt` |
| 키워드 태그 | `match_keywords`(JSON) |
| AI 매칭률 | `match_score` |
| 북마크 아이콘 | `bookmark_yn` |
| AI 요약 버튼 | `ai_summary` |

---

## 1단계 — DB 스키마

### 1-1. `tb_pre_specs` 신설

```sql
CREATE TABLE tb_pre_specs
(
    BF_SPEC_RGST_NO      VARCHAR(40)                           NOT NULL COMMENT '사전규격등록번호 (PK)',

    -- 공고 기본 정보
    BSNS_DIV_NM          VARCHAR(20)                           NULL COMMENT '업무구분명 (물품/용역/공사/외자)',
    REF_NO               VARCHAR(105)                          NULL COMMENT '참조번호',
    PRDCT_CLSFC_NO_NM    VARCHAR(200)                          NULL COMMENT '품목/용역분류명 (공고명 역할)',
    ORDER_INSTT_NM       VARCHAR(200)                          NULL COMMENT '발주기관명',
    RL_DMINSTT_NM        VARCHAR(200)                          NULL COMMENT '실수요기관명',
    ASIGN_BDGT_AMT       BIGINT                                NULL COMMENT '배정예산금액(원)',
    RCPT_DT              DATETIME                              NULL COMMENT '접수일시',
    OPNIN_RGST_CLSE_DT   DATETIME                              NULL COMMENT '의견등록마감일시 (입찰마감 역할)',
    OFCL_TEL_NO          VARCHAR(25)                           NULL COMMENT '담당자전화번호',
    OFCL_NM              VARCHAR(35)                           NULL COMMENT '담당자명',
    SW_BIZ_OBJ_YN        VARCHAR(1)   DEFAULT 'N'              NOT NULL COMMENT 'SW사업여부 (Y/N)',
    DLVR_TMLMT_DT        DATETIME                              NULL COMMENT '납품기한일시',
    DLVR_DAYNUM          INT                                   NULL COMMENT '납품일수',

    -- 파일
    SPEC_DOC_FILE_URLS   JSON                                  NULL COMMENT '규격문서파일 URL 목록 (최대 5개)',
    HAS_SPEC_DOC         TINYINT(1)   DEFAULT 0                NULL COMMENT '규격서 보유 여부',
    PRDCT_DTL_LIST       VARCHAR(4000)                         NULL COMMENT '품목상세목록 원본 ([번호^코드^품목명],...)',

    -- 연관 정보
    BID_NTCE_NO_LIST     VARCHAR(1000)                         NULL COMMENT '연관 입찰공고번호 목록 (콤마 구분)',
    RGST_DT              DATETIME                              NULL COMMENT '등록일시',
    CHG_DT               DATETIME                              NULL COMMENT '변경일시',

    -- 파일 처리 (converter + Dify 업로드)
    FILE_STATUS          VARCHAR(20)  DEFAULT 'PENDING'        NULL COMMENT '파일처리상태 PENDING/PROCESSING/DONE/FAILED/SKIPPED',
    FILE_PROCESSED_AT    DATETIME                              NULL COMMENT '파일처리완료일시',
    FILE_ERROR_MSG       VARCHAR(500)                          NULL COMMENT '파일처리실패사유',

    -- 키워드 추출
    KEYWORDS             JSON                                  NULL COMMENT '추출 키워드 배열',
    KEYWORD_STATUS       VARCHAR(20)  DEFAULT 'PENDING'        NULL COMMENT '키워드추출상태 PENDING/DONE/FAILED',
    KEYWORD_EXTRACTED_AT DATETIME                              NULL COMMENT '키워드추출완료일시',
    DIFY_DOC_ID          VARCHAR(100)                          NULL COMMENT 'Dify 지식DB 문서ID',

    -- AI 요약 (UI: AI 요약 버튼)
    AI_SUMMARY           MEDIUMTEXT                            NULL COMMENT 'AI 요약문',

    -- 메타
    RAW_JSON             LONGTEXT                              NULL COMMENT '원본 JSON',
    CREATED_AT           DATETIME     DEFAULT CURRENT_TIMESTAMP NULL,
    UPDATED_AT           DATETIME     DEFAULT CURRENT_TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (BF_SPEC_RGST_NO)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '나라장터 사전규격 공고';

CREATE INDEX idx_pre_specs_rcpt_dt           ON tb_pre_specs (RCPT_DT);
CREATE INDEX idx_pre_specs_opnin_clse_dt     ON tb_pre_specs (OPNIN_RGST_CLSE_DT);
CREATE INDEX idx_pre_specs_file_status       ON tb_pre_specs (FILE_STATUS);
CREATE INDEX idx_pre_specs_keyword_status    ON tb_pre_specs (KEYWORD_STATUS);
CREATE INDEX idx_pre_specs_order_instt       ON tb_pre_specs (ORDER_INSTT_NM);
CREATE INDEX idx_pre_specs_bsns_div_nm       ON tb_pre_specs (BSNS_DIV_NM);
CREATE INDEX idx_pre_specs_sw_biz_obj_yn     ON tb_pre_specs (SW_BIZ_OBJ_YN);
```

### 1-2. `tb_pre_specs_company_mapping` 신설

```sql
CREATE TABLE tb_pre_specs_company_mapping
(
    COMPANY_ID          BIGINT        NOT NULL COMMENT '기업ID',
    BF_SPEC_RGST_NO     VARCHAR(40)   NOT NULL COMMENT '사전규격등록번호',

    MATCH_TYPE_CD       VARCHAR(20)   NOT NULL DEFAULT 'AI'  COMMENT '매칭유형 (AI/MANUAL)',
    MATCH_SCORE         DECIMAL(5,4)  NULL COMMENT '매칭점수 (0.0000~1.0000)',
    MATCH_REASON        VARCHAR(1000) NULL COMMENT '매칭사유',
    MATCH_KEYWORDS      JSON          NULL COMMENT '매칭 키워드 (items/item_names/keywords/rag)',
    REASON_STATUS       VARCHAR(20)   NOT NULL DEFAULT 'PENDING' COMMENT '추천이유 생성상태 PENDING/DONE/FAILED',
    BOOKMARK_YN         VARCHAR(1)    NOT NULL DEFAULT 'N'   COMMENT '북마크 여부',
    LAST_MATCH_DT       DATETIME      NULL COMMENT '마지막 매칭일시',

    CREATED_AT          DATETIME      DEFAULT CURRENT_TIMESTAMP NULL,
    UPDATED_AT          DATETIME      DEFAULT CURRENT_TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT UK_pre_specs_company UNIQUE (COMPANY_ID, BF_SPEC_RGST_NO)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '기업-사전규격 매칭';

CREATE INDEX IDX_pre_specs_mapping_01 ON tb_pre_specs_company_mapping (COMPANY_ID, BOOKMARK_YN);
CREATE INDEX IDX_pre_specs_mapping_02 ON tb_pre_specs_company_mapping (BF_SPEC_RGST_NO);
CREATE INDEX IDX_pre_specs_mapping_03 ON tb_pre_specs_company_mapping (MATCH_TYPE_CD, LAST_MATCH_DT);
CREATE INDEX IDX_pre_specs_mapping_04 ON tb_pre_specs_company_mapping (REASON_STATUS);
```

---

## 2단계 — 모델 추가 (`bid-sync/models.py`)

- [ ] `PreSpec` 클래스 추가 (tb_pre_specs 매핑)
- [ ] `PreSpecCompanyMapping` 클래스 추가 (tb_pre_specs_company_mapping 매핑)

**핵심 차이점 (Bid 모델 대비):**
- PK: `bf_spec_rgst_no` 단일 PK (복합키 아님)
- `spec_doc_file_urls`: JSON (URL 배열, 최대 5개)
- `has_spec_doc`: Boolean (has_rfp 역할)
- `prdct_dtl_list`: String (원본 그대로 저장, 파싱은 서비스 레이어)
- `opnin_rgst_clse_dt`: DateTime (의견마감일, bid_clse_dt 역할)
- `ai_summary`: Text 추가

---

## 3단계 — G2B 클라이언트 확장 (`bid-sync/services/g2b_client.py`)

`fetch_pre_specs(bsns_div_list: list[str])` 함수 추가

- **Base URL**: `http://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService`
- **수집 대상 오퍼레이션**:
  - `getPublicPrcureThngInfoServc` — 용역 (IT 서비스)
  - `getPublicPrcureThngInfoThng` — 물품 (선택)
- **파라미터**: `inqryDiv=1` (등록일시 기준), 직전 10분 구간, `numOfRows=100`
- **페이징**: `_fetch_page()` 공통 유틸 재사용
- **정렬**: `rcptDt` 기준 내림차순

**응답 파싱 포인트:**
- `specDocFileUrl1` ~ `specDocFileUrl5` → 빈 문자열 제거 후 JSON 배열로 저장
- `prdctDtlList` → 원본 문자열 그대로 저장
- `bidNtceNoList` → 원본 그대로 저장 (콤마 구분 문자열)
- 환경변수: `G2B_PRE_SPEC_SERVICE_KEY` (없으면 `G2B_SERVICE_KEY` 폴백)

---

## 4단계 — 라우터 신설 (`bid-sync/router/pre_specs.py`)

```
POST /pre-specs/sync
POST /pre-specs/process-files?limit=50
POST /pre-specs/extract-keywords?limit=50
```

### `POST /pre-specs/sync`
- `fetch_pre_specs(["Servc", "Thng"])` 호출
- `bf_spec_rgst_no` 기준 기존 레코드 조회 (N+1 제거)
- 신규만 insert (`file_status`: 규격서 있으면 `PENDING`, 없으면 `SKIPPED`)
- Response: `{total, inserted, skipped}`

### `POST /pre-specs/process-files?limit=50`
- `file_status=PENDING` 레코드 조회
- `spec_doc_file_urls` 첫 번째 URL → HWP/PDF 변환 + Dify 업로드
  - 변환 성공 → `file_status=DONE`, `dify_doc_id` 저장
  - 변환 실패 → `file_status=FAILED`, `file_error_msg` 저장
- **기존 `converter.py`, `dify_client.py` 재사용**
- ALLOWED_HOSTS에 `www.g2b.go.kr` 이미 포함되어 있음 (확인 필요)

### `POST /pre-specs/extract-keywords?limit=50`
- `file_status=DONE`, `keyword_status=PENDING` 레코드 조회
- **기존 `dify_client.run_keyword_workflow()` 재사용**
- `keyword_status=DONE/FAILED`, `keywords` 저장

---

## 5단계 — 매칭 확장

### `bid-sync/services/matcher.py`
`match_company_pre_spec(company_id, db)` 함수 추가

- 기존 `match_company()` 로직과 동일한 가중치/임계값 적용
- 대상: `keyword_status IN (DONE, FAILED)` + `opnin_rgst_clse_dt` 미래인 것
- `prdct_dtl_list` 파싱 → 품목 코드 추출 (`W_ITEM` 계산)
- 매칭 결과 → `tb_pre_specs_company_mapping` upsert
- `usage_limiter.py`의 `PRESPEC_RECOMMEND` 제한 체크 (개발현황.md 4-④ 항목)

### `bid-sync/router/matching.py`
```
POST /matching/run-pre-specs               # 사전규격 기업 매칭 실행
POST /matching/generate-pre-spec-reasons   # PENDING 추천이유 생성
```

---

## 6단계 — 스케줄링 체인 확장

```
POST /pre-specs/sync
  → POST /pre-specs/process-files?limit=50
    → POST /pre-specs/extract-keywords?limit=50
      → POST /matching/run-pre-specs
        → POST /matching/generate-pre-spec-reasons?limit=50
```

기존 입찰공고 체인과 별도로 운영 (Dify Schedule에 추가)

---

## 7단계 — `main.py` 라우터 등록

```python
from router.pre_specs import router as pre_specs_router
app.include_router(pre_specs_router)
```

---

## 8단계 — `doc/db/company.sql` 업데이트

- `tb_pre_specs` DDL 추가
- `tb_pre_specs_company_mapping` DDL 추가

---

## 환경변수 추가

```
G2B_PRE_SPEC_SERVICE_KEY      # 사전규격 API 서비스키 (없으면 G2B_SERVICE_KEY 폴백)
DIFY_PRE_SPEC_DATASET_ID      # 사전규격 전용 Dify 지식DB ID (입찰공고 DIFY_DATASET_ID와 별도)
```

---

## 구현 체크리스트

### DB / 모델
- [x] `doc/db/company.sql` — 테이블 DDL 추가
- [x] `bid-sync/models.py` — `PreSpec`, `PreSpecCompanyMapping` 모델 추가

### 수집
- [x] `bid-sync/services/g2b_client.py` — `fetch_pre_specs()` 추가
- [x] `bid-sync/services/dify_client.py` — `upload_pre_spec_to_knowledge()` 추가
- [x] `bid-sync/locks.py` — 사전규격 전용 lock 3개 추가
- [x] `bid-sync/router/pre_specs.py` — 신설 (`sync`, `process-files`, `extract-keywords`)
- [x] `bid-sync/main.py` — 라우터 등록

### 매칭
- [x] `bid-sync/services/matcher.py` — `match_company_pre_spec()`, `_parse_prdct_dtl_list()`, `_get_active_pre_specs()` 추가
- [x] `bid-sync/router/matching.py` — `run-pre-specs`, `run-pre-specs/{company_id}`, `generate-pre-spec-reasons` 추가
- [x] `bid-sync/services/usage_limiter.py` — `PRESPEC_RECOMMEND` 이미 구현됨 (확인 완료)

---

## 주요 설계 규칙 (기존과 동일)

```python
# 매칭 가중치
W_ITEM    = 0.40
W_KEYWORD = 0.35
W_RFP_RAG = 0.25

# 저장 임계값
MIN_SCORE = 0.40

# 파일처리: spec_doc_file_urls[0] 만 처리 (첫 번째 규격서)
# keyword_status=FAILED 공고도 매칭 대상 (공고명 fallback)
```

---

## 수집 업무구분 결정 (TODO)

- [x] **용역(Servc)** — IT 서비스, 소프트웨어 개발 포함, 기본 수집
- [ ] **물품(Thng)** — 하드웨어/장비 구매, 추후 결정
- [ ] 공사(Cnstwk) / 외자(Frgcpt) — 제외