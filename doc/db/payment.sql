-- ============================================================
-- DROP
-- ============================================================
# DROP TABLE IF EXISTS tb_payment_cancel;
# DROP TABLE IF EXISTS tb_payment_result;
# DROP TABLE IF EXISTS tb_payment_order;
# DROP TABLE IF EXISTS tb_billing_key;
# DROP TABLE IF EXISTS tb_billing_profile;
# DROP TABLE IF EXISTS tb_subscription;
# DROP TABLE IF EXISTS tb_subscription_plan;


-- ============================================================
-- 1. 구독 플랜
-- ============================================================
CREATE TABLE tb_subscription_plan
(
    ID                 BIGINT       NOT NULL AUTO_INCREMENT COMMENT '플랜 PK',
    PLAN_NM            VARCHAR(100) NULL     COMMENT '월간 구독, 연간 구독-1년 등',
    PERIOD_GROUP       VARCHAR(20)  NULL     COMMENT '구독 기간 그룹 (MONTH, YEAR)',
    PERIOD_MONTH       INT          NULL     COMMENT '1, 12, 24, 36',
    TOTAL_PRICE   int          default 0               null comment '부가세 포함 판매가 (공급가 + VAT 10%)',
    PRICE              INT          NULL     COMMENT '공급가',
    ORIGIN_PRICE       INT          NULL     COMMENT '원가 (할인 전)',
    DISCOUNT_RATE      INT          NULL     COMMENT '할인율 10, 15 등',
    DESCRIPTION        VARCHAR(200) NULL     COMMENT '카드 설명 텍스트',
    SORT_NUM           INT          NULL     COMMENT '화면 정렬 순서',
    USE_YN             CHAR         NULL     COMMENT '사용 여부',
    CREATED_AT         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    UPDATED_AT         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    PRIMARY KEY (ID)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci
    COMMENT ='구독 플랜 정의';

insert into tb_subscription_plan (ID, PLAN_NM, PERIOD_GROUP, PERIOD_MONTH, PRICE, ORIGIN_PRICE, DISCOUNT_RATE, DESCRIPTION, SORT_NUM, USE_YN, CREATED_AT, UPDATED_AT, TOTAL_PRICE)
values  (1, 'Pro',      'MONTH', 1,  500000,  0,        0,  '프리랜서 및 1인 컨설턴트를 위한 최적의 플랜입니다.', 1, 'Y', '2026-04-09 10:48:17', '2026-04-09 10:48:17', 0),
        (2, 'Business', 'MONTH', 1,  1000000, 0,        0,  '협업 기능이 필요한 팀을 위한 플랜입니다.',         2, 'Y', '2026-04-09 10:48:17', '2026-04-09 10:48:17', 0),
        (3, 'Pro',      'YEAR',  12, 5400000, 6000000,  10, '프리랜서 및 1인 컨설턴트를 위한 최적의 플랜입니다.', 3, 'Y', '2026-04-09 10:48:17', '2026-04-09 10:48:17', 0),
        (4, 'Business', 'YEAR',  12, 9600000, 12000000, 20, '협업 기능이 필요한 팀을 위한 플랜입니다.',         4, 'Y', '2026-04-09 10:48:17', '2026-04-09 10:48:17', 0),
        (5, 'Free',     'FREE',  0,  0,       0,        0,  '서비스를 무료로 체험할 수 있는 기본 플랜입니다.',   0, 'Y', '2026-04-21 00:00:00', '2026-04-21 00:00:00', 0)
;

UPDATE tb_subscription_plan SET TOTAL_PRICE = PRICE * 1.1 WHERE PERIOD_GROUP != 'FREE';

-- ============================================================
-- 1-2. 플랜 제한값 컬럼 추가
-- ============================================================
ALTER TABLE tb_subscription_plan
    ADD COLUMN ALARM_KAKAO_DAY_LIMIT        INT NULL COMMENT '실시간 알림(카카오) 일 제한 (NULL=무제한)',
    ADD COLUMN BID_RECOMMEND_DAY_LIMIT      INT NULL COMMENT '입찰 공고 추천 일 제한 (NULL=무제한)',
    ADD COLUMN PRESPEC_RECOMMEND_DAY_LIMIT  INT NULL COMMENT '사전규격 공고 추천 일 제한 (NULL=무제한)',
    ADD COLUMN AI_SUMMARY_DAY_LIMIT         INT NULL COMMENT 'AI 요약 일 제한 - Free 전용 (NULL=월 단위 or 무제한)',
    ADD COLUMN AI_SUMMARY_MONTH_LIMIT       INT NULL COMMENT 'AI 요약 월 제한 - Pro/Business (NULL=무제한)',
    ADD COLUMN AI_SEARCH_DAY_LIMIT          INT NULL COMMENT 'AI 검색 일 제한 (NULL=무제한)';

-- Free (ID=5)
UPDATE tb_subscription_plan
SET ALARM_KAKAO_DAY_LIMIT       = 1,
    BID_RECOMMEND_DAY_LIMIT     = 15,
    PRESPEC_RECOMMEND_DAY_LIMIT = 5,
    AI_SUMMARY_DAY_LIMIT        = 5,
    AI_SUMMARY_MONTH_LIMIT      = NULL,
    AI_SEARCH_DAY_LIMIT         = 3
WHERE ID = 5;

-- Pro MONTH (ID=1), Pro YEAR (ID=3)
UPDATE tb_subscription_plan
SET ALARM_KAKAO_DAY_LIMIT       = 10,
    BID_RECOMMEND_DAY_LIMIT     = 15,
    PRESPEC_RECOMMEND_DAY_LIMIT = 5,
    AI_SUMMARY_DAY_LIMIT        = NULL,
    AI_SUMMARY_MONTH_LIMIT      = 100,
    AI_SEARCH_DAY_LIMIT         = NULL
WHERE ID IN (1, 3);

-- Business MONTH (ID=2), Business YEAR (ID=4)
UPDATE tb_subscription_plan
SET ALARM_KAKAO_DAY_LIMIT       = 20,
    BID_RECOMMEND_DAY_LIMIT     = 25,
    PRESPEC_RECOMMEND_DAY_LIMIT = 5,
    AI_SUMMARY_DAY_LIMIT        = NULL,
    AI_SUMMARY_MONTH_LIMIT      = 200,
    AI_SEARCH_DAY_LIMIT         = NULL
WHERE ID IN (2, 4);

-- Enterprise: 모든 제한 NULL (무제한) — 추후 ID 확정 시 INSERT

-- ============================================================
-- 2. 구독
-- ============================================================
CREATE TABLE tb_subscription
(
    ID                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '구독 PK',
    USER_ID           VARCHAR(50)  NOT NULL COMMENT '회원 ID',
    PLAN_ID           BIGINT       NOT NULL COMMENT '구독 플랜 ID',
    STATUS            VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE' COMMENT '구독 상태 (ACTIVE / PAUSED / CANCELED / EXPIRED)',
    NEXT_BILLING_DATE DATE         NOT NULL COMMENT '다음 결제 예정일',
    STARTED_AT        DATE         NOT NULL COMMENT '구독 시작일',
    ENDED_AT          DATE         NULL     COMMENT '구독 종료일',
    CANCELED_AT       DATETIME     NULL     COMMENT '해지 요청 일시',
    CANCEL_REASON     VARCHAR(500) NULL     COMMENT '해지 사유',
    CREATED_AT        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    UPDATED_AT        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    PRIMARY KEY (ID),
    KEY idx_sub_user_id (USER_ID),
    KEY idx_sub_plan_id (PLAN_ID),
    KEY idx_sub_next_billing (NEXT_BILLING_DATE, STATUS)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci
    COMMENT ='회원 구독 정보';


-- ============================================================
-- 3. 빌링키
-- ============================================================
CREATE TABLE tb_billing_key
(
    ID                  BIGINT       NOT NULL AUTO_INCREMENT COMMENT '빌링키 PK',
    USER_ID             VARCHAR(50)  NOT NULL COMMENT '회원 ID',
    CUSTOMER_KEY        VARCHAR(300) NOT NULL COMMENT '토스 구매자 ID',
    BILLING_KEY         VARCHAR(500) NOT NULL COMMENT '토스 발급 빌링키',
    METHOD              VARCHAR(20)  NOT NULL COMMENT '결제수단 (CARD / TRANSFER)',
    CARD_COMPANY        VARCHAR(50)  NULL     COMMENT '카드사명',
    CARD_NUMBER         VARCHAR(30)  NULL     COMMENT '마스킹된 카드번호',
    CARD_TYPE           VARCHAR(10)  NULL     COMMENT '카드 종류 (신용 / 체크)',
    CARD_OWNER_TYPE     VARCHAR(10)  NULL     COMMENT '카드 소유자 유형 (개인 / 법인)',
    BANK_NAME           VARCHAR(50)  NULL     COMMENT '은행명',
    BANK_ACCOUNT_NUMBER VARCHAR(50)  NULL     COMMENT '마스킹된 계좌번호',
    IS_DEFAULT          TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '기본 결제수단 여부',
    STATUS              TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '활성 여부',
    AUTHENTICATED_AT    DATETIME     NULL     COMMENT '카드 인증 일시',
    CREATED_AT          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    UPDATED_AT          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    PRIMARY KEY (ID),
    UNIQUE KEY uq_billing_key (BILLING_KEY),
    KEY idx_bk_user_id (USER_ID),
    KEY idx_bk_customer_key (CUSTOMER_KEY)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci
    COMMENT ='토스페이먼츠 빌링키';


-- ============================================================
-- 4. 결제 주문
-- ============================================================
CREATE TABLE tb_payment_order
(
    ID              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '결제 주문 PK',
    SUBSCRIPTION_ID BIGINT       NOT NULL COMMENT '구독 ID',
    BILLING_KEY_ID  BIGINT       NOT NULL COMMENT '빌링키 ID',
    ORDER_ID        VARCHAR(64)  NOT NULL COMMENT '주문 ID (UUID)',
    ORDER_NAME      VARCHAR(100) NOT NULL COMMENT '주문명',
    AMOUNT          INT          NOT NULL COMMENT '결제 요청 금액',
    STATUS          VARCHAR(20)  NOT NULL DEFAULT 'PENDING' COMMENT '결제 주문 상태 (PENDING / DONE / FAILED / CANCELED)',
    SCHEDULED_AT    DATETIME     NOT NULL COMMENT '결제 예약 일시',
    CREATED_AT      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    UPDATED_AT      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    PRIMARY KEY (ID),
    UNIQUE KEY uq_order_id (ORDER_ID),
    KEY idx_po_subscription_id (SUBSCRIPTION_ID),
    KEY idx_po_billing_key_id (BILLING_KEY_ID),
    KEY idx_po_status_scheduled (STATUS, SCHEDULED_AT)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci
    COMMENT ='결제 주문';


-- ============================================================
-- 5. 결제 결과
-- ============================================================
CREATE TABLE tb_payment_result
(
    ID                     BIGINT       NOT NULL AUTO_INCREMENT COMMENT '결제 결과 PK',
    PAYMENT_ORDER_ID       BIGINT       NOT NULL COMMENT '결제 주문 ID',
    PAYMENT_KEY            VARCHAR(200) NOT NULL COMMENT '토스 paymentKey',
    TOSS_STATUS            VARCHAR(20)  NOT NULL COMMENT '토스 결제 상태',
    METHOD                 VARCHAR(20)  NULL     COMMENT '결제수단',
    CARD_ISSUER_CODE       VARCHAR(10)  NULL     COMMENT '카드 발급사 코드',
    CARD_ACQUIRER_CODE     VARCHAR(10)  NULL     COMMENT '카드 매입사 코드',
    CARD_NUMBER            VARCHAR(30)  NULL     COMMENT '마스킹된 카드번호',
    CARD_TYPE              VARCHAR(10)  NULL     COMMENT '카드 종류',
    CARD_OWNER_TYPE        VARCHAR(10)  NULL     COMMENT '카드 소유자 유형',
    CARD_APPROVE_NO        VARCHAR(20)  NULL     COMMENT '카드사 승인번호',
    CARD_ACQUIRE_STATUS    VARCHAR(20)  NULL     COMMENT '매입 상태',
    TRANSFER_BANK_CODE     VARCHAR(10)  NULL     COMMENT '이체 은행 코드',
    TRANSFER_SETTLE_STATUS VARCHAR(20)  NULL     COMMENT '정산 상태',
    TOTAL_AMOUNT           INT          NOT NULL DEFAULT 0 COMMENT '총 결제 금액',
    BALANCE_AMOUNT         INT          NOT NULL DEFAULT 0 COMMENT '취소 가능 잔액',
    SUPPLIED_AMOUNT        INT          NOT NULL DEFAULT 0 COMMENT '공급가액',
    VAT                    INT          NOT NULL DEFAULT 0 COMMENT '부가세',
    TAX_FREE_AMOUNT        INT          NOT NULL DEFAULT 0 COMMENT '비과세 금액',
    RECEIPT_URL            VARCHAR(500) NULL     COMMENT '영수증 URL',
    FAILURE_CODE           VARCHAR(100) NULL     COMMENT '토스 에러 코드',
    FAILURE_MESSAGE        VARCHAR(500) NULL     COMMENT '토스 에러 메시지',
    TOSS_REQUESTED_AT      VARCHAR(30)  NULL     COMMENT '결제 요청 시간',
    TOSS_APPROVED_AT       VARCHAR(30)  NULL     COMMENT '결제 승인 시간',
    CREATED_AT             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',

    PRIMARY KEY (ID),
    UNIQUE KEY uq_payment_key (PAYMENT_KEY),
    UNIQUE KEY uq_payment_order_id (PAYMENT_ORDER_ID)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci
    COMMENT ='토스페이먼츠 결제 결과';


-- ============================================================
-- 6. 결제 취소 이력
-- ============================================================
CREATE TABLE tb_payment_cancel
(
    ID                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '취소 이력 PK',
    PAYMENT_RESULT_ID BIGINT       NOT NULL COMMENT '결제 결과 ID',
    CANCEL_AMOUNT     INT          NOT NULL COMMENT '취소 금액',
    CANCEL_REASON     VARCHAR(200) NOT NULL COMMENT '취소 사유',
    TRANSACTION_KEY   VARCHAR(200) NULL     COMMENT '취소 거래 키',
    TOSS_CANCELED_AT  VARCHAR(30)  NULL     COMMENT '취소 완료 시간',
    CREATED_AT        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',

    PRIMARY KEY (ID),
    KEY idx_pc_payment_result_id (PAYMENT_RESULT_ID)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci
    COMMENT ='결제 취소 이력';


-- ============================================================
-- 7. 청구 프로필
-- ============================================================
CREATE TABLE tb_billing_profile
(
    USER_ID          VARCHAR(50)  NOT NULL COMMENT '회원 ID (PK)',
    BILLING_NAME     VARCHAR(100) NOT NULL COMMENT '이름 또는 회사명',
    BILLING_EMAIL    VARCHAR(200) NOT NULL COMMENT '인보이스 수신 이메일',
    BILLING_ADDRESS  VARCHAR(300) NULL     COMMENT '청구 주소',
    BILLING_ADDRESS2 VARCHAR(300) NULL     COMMENT '상세 주소',
    CREATED_AT       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    UPDATED_AT       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    PRIMARY KEY (USER_ID)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci
    COMMENT ='청구 프로필';


-- ============================================================
-- 8. 플랜 사용량 일별 집계
-- ============================================================
CREATE TABLE tb_subscription_usage_daily
(
    USER_ID      VARCHAR(50) NOT NULL COMMENT '회원 ID',
    FEATURE_TYPE VARCHAR(30) NOT NULL COMMENT '기능 구분 (ALARM_KAKAO | AI_SUMMARY | AI_SEARCH)',
    USE_DT       DATE        NOT NULL COMMENT '사용 날짜 (일별 자동 분리)',
    USE_COUNT    INT         NOT NULL DEFAULT 0 COMMENT '당일 누적 사용 횟수',
    UPDATED_AT   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP COMMENT '최종 갱신 일시',

    PRIMARY KEY (USER_ID, FEATURE_TYPE, USE_DT),
    KEY idx_usage_user_dt (USER_ID, USE_DT)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci
    COMMENT ='구독 플랜 기능별 일별 사용량';


-- ============================================================
-- 9. 구독/빌링 테이블 USER_ID → COMPANY_ID 변경
-- ============================================================
ALTER TABLE tb_subscription
    DROP COLUMN USER_ID,
    ADD COLUMN COMPANY_ID BIGINT NOT NULL COMMENT '기업 ID' AFTER ID,
    ADD KEY idx_sub_company_id (COMPANY_ID);

ALTER TABLE tb_billing_key
    DROP COLUMN USER_ID,
    ADD COLUMN COMPANY_ID BIGINT NOT NULL COMMENT '기업 ID' AFTER ID,
    ADD KEY idx_bk_company_id (COMPANY_ID);

ALTER TABLE tb_billing_profile
    DROP PRIMARY KEY,
    DROP COLUMN USER_ID,
    ADD COLUMN COMPANY_ID BIGINT NOT NULL COMMENT '기업 ID' FIRST,
    ADD PRIMARY KEY (COMPANY_ID);

ALTER TABLE tb_subscription_usage_daily
    DROP PRIMARY KEY,
    DROP COLUMN USER_ID,
    ADD COLUMN COMPANY_ID BIGINT NOT NULL COMMENT '기업 ID' FIRST,
    ADD PRIMARY KEY (COMPANY_ID, FEATURE_TYPE, USE_DT),
    ADD KEY idx_usage_company_dt (COMPANY_ID, USE_DT);