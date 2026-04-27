CREATE TABLE tb_bids
(
    BID_NTCE_NO          VARCHAR(40)                           NOT NULL COMMENT '공고번호',
    BID_NTCE_ORD         VARCHAR(10)                           NOT NULL COMMENT '공고차수',
    BID_NTCE_NM          VARCHAR(300)                          NULL COMMENT '공고명',
    NTCE_INSTT_CD        VARCHAR(20)                           NULL COMMENT '공고기관코드',
    NTCE_INSTT_NM        VARCHAR(200)                          NULL COMMENT '공고기관명',
    DMND_INSTT_NM        VARCHAR(200)                          NULL COMMENT '수요기관명',
    BID_NTCE_DT          VARCHAR(20)                           NULL COMMENT '공고일시',
    BID_CLSE_DT          VARCHAR(20)                           NULL COMMENT '입찰마감일시',
    OPENG_DT             VARCHAR(20)                           NULL COMMENT '개찰일시',
    BID_MTD_NM           VARCHAR(100)                          NULL COMMENT '입찰방법',
    CNTRCT_CNCLSN_MTD_NM VARCHAR(100)                          NULL COMMENT '계약방법',
    PRESMPT_PRCE         BIGINT                                NULL COMMENT '추정가격(원)',
    BID_CLSFCTN_NO       VARCHAR(20)                           NULL COMMENT '입찰분류번호(품목코드)',
    BID_KIND             VARCHAR(100)                          NULL COMMENT '공고종류',
    DETAIL_URL           TEXT                                  NULL COMMENT '공고 상세링크',
    SRVCE_DIV_NM         VARCHAR(100)                          NULL COMMENT '서비스구분명 (기술용역 등)',
    IS_MOCK_YN           VARCHAR(1)   DEFAULT 'N'              NOT NULL COMMENT '모의공고여부 (공고번호 T로 시작 시 Y)',
    IS_URGENT_YN         VARCHAR(1)   DEFAULT 'N'              NOT NULL COMMENT '긴급공고여부 (공고명 긴급 포함 시 Y)',
    HAS_RFP              TINYINT(1)  DEFAULT 0                 NULL COMMENT 'RFP 포함 여부',
    RFP_FILE_URL         TEXT                                  NULL COMMENT 'RFP 파일 URL (대표 1개)',
    FILE_URLS            JSON                                  NULL COMMENT '전체 첨부파일 URL 목록',
    FILE_STATUS          VARCHAR(20) DEFAULT 'PENDING'         NULL COMMENT '파일처리상태: PENDING/PROCESSING/DONE/FAILED/SKIPPED',
    FILE_PROCESSED_AT    DATETIME                              NULL COMMENT '파일처리 완료일시',
    FILE_ERROR_MSG       VARCHAR(500)                          NULL COMMENT '파일처리 실패사유',
    KEYWORDS             JSON                                  NULL COMMENT '추출 키워드 배열',
    KEYWORD_STATUS       VARCHAR(20) DEFAULT 'PENDING'         NULL COMMENT '키워드추출상태: PENDING/DONE/FAILED',
    KEYWORD_EXTRACTED_AT DATETIME                              NULL COMMENT '키워드추출 완료일시',
    DIFY_DOC_ID          VARCHAR(100)                          NULL COMMENT 'Dify 지식DB 문서ID',
    RAW_JSON             LONGTEXT                              NULL COMMENT '원본 JSON',
    CREATED_AT           DATETIME    DEFAULT CURRENT_TIMESTAMP NULL,
    UPDATED_AT           DATETIME    DEFAULT CURRENT_TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (BID_NTCE_NO, BID_NTCE_ORD)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT = '나라장터 입찰공고';

CREATE INDEX idx_bids_bid_ntce_dt    ON tb_bids (BID_NTCE_DT);
CREATE INDEX idx_bids_bid_clse_dt    ON tb_bids (BID_CLSE_DT);
CREATE INDEX idx_bids_has_rfp        ON tb_bids (HAS_RFP);
CREATE INDEX idx_bids_file_status    ON tb_bids (FILE_STATUS);
CREATE INDEX idx_bids_keyword_status ON tb_bids (KEYWORD_STATUS);
CREATE INDEX idx_bids_ntce_instt     ON tb_bids (NTCE_INSTT_NM);
CREATE INDEX idx_bids_clsfctn_no     ON tb_bids (BID_CLSFCTN_NO);

CREATE TABLE tb_bids_company_mapping
(
    COMPANY_ID     BIGINT        NOT NULL COMMENT '기업ID',
    BID_NTCE_NO    VARCHAR(40)   NOT NULL COMMENT '공고번호',
    BID_NTCE_ORD   VARCHAR(10)   NOT NULL COMMENT '공고차수',

    MATCH_TYPE_CD  VARCHAR(20)   NOT NULL DEFAULT 'AI' COMMENT '매칭유형 (AI/MANUAL)',
    MATCH_SCORE    DECIMAL(5, 4) NULL COMMENT '매칭점수 (0.0000~1.0000)',
    MATCH_REASON   VARCHAR(1000) NULL COMMENT '매칭사유',
    MATCH_KEYWORDS JSON          NULL COMMENT '매칭 키워드 배열',
    BOOKMARK_YN    VARCHAR(1)    NOT NULL DEFAULT 'N' COMMENT '북마크 여부',

    LAST_MATCH_DT  DATETIME      NULL COMMENT '마지막 매칭일시',

    CONSTRAINT UK_bids_company_mapping UNIQUE (COMPANY_ID, BID_NTCE_NO, BID_NTCE_ORD)
) COMMENT = '기업-공고 매칭' CHARSET = utf8mb4;

CREATE INDEX IDX_bids_company_mapping_01 ON tb_bids_company_mapping (COMPANY_ID, BOOKMARK_YN);
CREATE INDEX IDX_bids_company_mapping_02 ON tb_bids_company_mapping (BID_NTCE_NO, BID_NTCE_ORD);
CREATE INDEX IDX_bids_company_mapping_03 ON tb_bids_company_mapping (MATCH_TYPE_CD, LAST_MATCH_DT);

ALTER TABLE tb_bids ADD COLUMN AI_SUMMARY MEDIUMTEXT NULL;
ALTER TABLE TB_BIDS_COMPANY_MAPPING ADD COLUMN AI_SUMMARY_YN CHAR(1) DEFAULT 'N';

-- ──────────────────────────────────────────
-- 사전규격 공고
-- ──────────────────────────────────────────

CREATE TABLE tb_pre_specs
(
    BF_SPEC_RGST_NO      VARCHAR(40)                           NOT NULL COMMENT '사전규격등록번호 (PK)',

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

    SPEC_DOC_FILE_URLS   JSON                                  NULL COMMENT '규격문서파일 URL 목록 (최대 5개)',
    HAS_SPEC_DOC         TINYINT(1)   DEFAULT 0                NULL COMMENT '규격서 보유 여부',
    PRDCT_DTL_LIST       VARCHAR(4000)                         NULL COMMENT '품목상세목록 원본 ([번호^코드^품목명],...)',

    BID_NTCE_NO_LIST     VARCHAR(1000)                         NULL COMMENT '연관 입찰공고번호 목록 (콤마 구분)',
    RGST_DT              DATETIME                              NULL COMMENT '등록일시',
    CHG_DT               DATETIME                              NULL COMMENT '변경일시',

    FILE_STATUS          VARCHAR(20)  DEFAULT 'PENDING'        NULL COMMENT '파일처리상태 PENDING/PROCESSING/DONE/FAILED/SKIPPED',
    FILE_PROCESSED_AT    DATETIME                              NULL COMMENT '파일처리완료일시',
    FILE_ERROR_MSG       VARCHAR(500)                          NULL COMMENT '파일처리실패사유',

    KEYWORDS             JSON                                  NULL COMMENT '추출 키워드 배열',
    KEYWORD_STATUS       VARCHAR(20)  DEFAULT 'PENDING'        NULL COMMENT '키워드추출상태 PENDING/DONE/FAILED',
    KEYWORD_EXTRACTED_AT DATETIME                              NULL COMMENT '키워드추출완료일시',
    DIFY_DOC_ID          VARCHAR(100)                          NULL COMMENT 'Dify 지식DB 문서ID',

    AI_SUMMARY           MEDIUMTEXT                            NULL COMMENT 'AI 요약문',

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

CREATE TABLE tb_pre_specs_company_mapping
(
    COMPANY_ID          BIGINT        NOT NULL COMMENT '기업ID',
    BF_SPEC_RGST_NO     VARCHAR(40)   NOT NULL COMMENT '사전규격등록번호',

    MATCH_TYPE_CD       VARCHAR(20)   NOT NULL DEFAULT 'AI'      COMMENT '매칭유형 (AI/MANUAL)',
    MATCH_SCORE         DECIMAL(5,4)  NULL     COMMENT '매칭점수 (0.0000~1.0000)',
    MATCH_REASON        VARCHAR(1000) NULL     COMMENT '매칭사유',
    MATCH_KEYWORDS      JSON          NULL     COMMENT '매칭 키워드 (items/item_names/keywords/rag)',
    REASON_STATUS       VARCHAR(20)   NOT NULL DEFAULT 'PENDING' COMMENT '추천이유 생성상태 PENDING/DONE/FAILED',
    BOOKMARK_YN         VARCHAR(1)    NOT NULL DEFAULT 'N'       COMMENT '북마크 여부',
    LAST_MATCH_DT       DATETIME      NULL     COMMENT '마지막 매칭일시',

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