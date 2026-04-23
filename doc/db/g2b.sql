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

