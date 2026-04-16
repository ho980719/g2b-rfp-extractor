-- 1. 기존 사용자 테이블 확장
ALTER TABLE tb_user_info
    ADD COLUMN KAKAO_ALARM_YN varchar(1)  NOT NULL DEFAULT 'N' COMMENT '카카오 알림 사용 여부' AFTER KAKAO_ID,
    ADD COLUMN EMAIL_AUTH_YN  varchar(1)  NOT NULL DEFAULT 'N' COMMENT '이메일 인증 여부' AFTER KAKAO_ALARM_YN,
    ADD COLUMN TEL_AUTH_YN    varchar(1)  NOT NULL DEFAULT 'N' COMMENT '연락처 인증 여부' AFTER EMAIL_AUTH_YN,
    ADD COLUMN USER_STATUS_CD varchar(20) NOT NULL DEFAULT 'ACTIVE' COMMENT '사용자 상태코드(ACTIVE/DORMANT/WITHDRAW)' AFTER TEL_AUTH_YN,
    ADD COLUMN LAST_LOGIN_DT  datetime DEFAULT NULL COMMENT '마지막 로그인일시' AFTER USER_STATUS_CD;


-- 2. 기업 기본정보
CREATE TABLE `tb_company_info`
(
    `COMPANY_ID`        bigint       NOT NULL AUTO_INCREMENT COMMENT '기업ID',
    `OWNER_USER_ID`     varchar(50)  NOT NULL COMMENT '대표 사용자ID',
    `COMPANY_NM`        varchar(200) NOT NULL COMMENT '상호명',
    `CEO_NM`            varchar(100)          DEFAULT NULL COMMENT '대표자명',
    `COMPANY_ADDR`      varchar(500)          DEFAULT NULL COMMENT '기업주소',
    `BIZ_NO`            varchar(20)           DEFAULT NULL COMMENT '사업자등록번호',
    `BIZ_AUTH_YN`       varchar(1)   NOT NULL DEFAULT 'N' COMMENT '사업자번호 인증여부',
    `COMPANY_STATUS_CD` varchar(20)  NOT NULL DEFAULT 'ACTIVE' COMMENT '기업상태코드',
    `DESCRIPTION`       varchar(500)          DEFAULT NULL COMMENT '비고',
    `USE_YN`            varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`            varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`            datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`            varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`            datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`COMPANY_ID`),
    UNIQUE KEY `UK_TB_COMPANY_INFO_01` (`BIZ_NO`),
    KEY `IDX_TB_COMPANY_INFO_01` (`OWNER_USER_ID`),
    KEY `IDX_TB_COMPANY_INFO_02` (`USE_YN`, `COMPANY_STATUS_CD`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='기업 기본정보';

CREATE TABLE `tb_company_homepage`
(
    `SEQ`          bigint       NOT NULL AUTO_INCREMENT COMMENT '순번',
    `COMPANY_ID`   bigint       NOT NULL COMMENT '기업ID',
    `HOMEPAGE_URL` varchar(500) NOT NULL COMMENT '홈페이지 URL',
    `SORT_ORD`     int          NOT NULL DEFAULT 1 COMMENT '정렬순서',
    `USE_YN`       varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`       varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`       datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`       varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`       datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`SEQ`),
    KEY `IDX_TB_COMPANY_HOMEPAGE_01` (`COMPANY_ID`, `USE_YN`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='기업 홈페이지';

-- 3. 기업 개인화 / 프로필
-- 2-1. 기업 프로필
CREATE TABLE `tb_company_profile`
(
    `COMPANY_ID`         bigint      NOT NULL COMMENT '기업ID',
    `BUSINESS_AREA`      varchar(500)         DEFAULT NULL COMMENT '사업분야',
    `SOLUTION_TECH_AREA` text COMMENT '솔루션 및 기술분야',
    `PERFORMANCE_DESC`   text COMMENT '수행실적',
    `PROFILE_SUMMARY`    text COMMENT '기업 요약 프로필',
    `AI_ANALYSIS_YN`     varchar(1)  NOT NULL DEFAULT 'N' COMMENT 'AI 분석 여부',
    `AI_ANALYSIS_DT`     datetime             DEFAULT NULL COMMENT 'AI 분석일시',
    `USE_YN`             varchar(1)  NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`             varchar(50) NOT NULL COMMENT '등록자ID',
    `REG_DT`             datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`             varchar(50)          DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`             datetime             DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`COMPANY_ID`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='기업 프로필';

-- 2-2. 기업 업종코드
CREATE TABLE `tb_company_industry`
(
    `SEQ`         bigint       NOT NULL AUTO_INCREMENT COMMENT '순번',
    `COMPANY_ID`  bigint       NOT NULL COMMENT '기업ID',
    `INDUSTRY_CD` varchar(50)  NOT NULL COMMENT '업종코드',
    `INDUSTRY_NM` varchar(200) NOT NULL COMMENT '업종명',
    `SORT_ORD`    int          NOT NULL DEFAULT 1 COMMENT '정렬순서',
    `USE_YN`      varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`      varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`      datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`      varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`      datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`SEQ`),
    KEY `IDX_TB_COMPANY_INDUSTRY_01` (`COMPANY_ID`, `USE_YN`),
    KEY `IDX_TB_COMPANY_INDUSTRY_02` (`INDUSTRY_CD`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='기업 업종코드';

-- 2-3. 기업 세부품명
CREATE TABLE `tb_company_item`
(
    `SEQ`        bigint       NOT NULL AUTO_INCREMENT COMMENT '순번',
    `COMPANY_ID` bigint       NOT NULL COMMENT '기업ID',
    `ITEM_CD`    varchar(50)  NOT NULL COMMENT '세부품명번호',
    `ITEM_NM`    varchar(200) NOT NULL COMMENT '세부품명명',
    `SORT_ORD`   int          NOT NULL DEFAULT 1 COMMENT '정렬순서',
    `USE_YN`     varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`     varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`     datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`     varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`     datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`SEQ`),
    KEY `IDX_TB_COMPANY_ITEM_01` (`COMPANY_ID`, `USE_YN`),
    KEY `IDX_TB_COMPANY_ITEM_02` (`ITEM_CD`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='기업 세부품명';

-- 3. 멤버 관리
CREATE TABLE `tb_company_member`
(
    `MEMBER_ID`        bigint       NOT NULL AUTO_INCREMENT COMMENT '멤버ID',
    `COMPANY_ID`       bigint       NOT NULL COMMENT '기업ID',
    `USER_ID`          varchar(50)           DEFAULT NULL COMMENT '사용자ID',
    `MEMBER_EMAIL`     varchar(100) NOT NULL COMMENT '멤버이메일',
    `MEMBER_NM`        varchar(100)          DEFAULT NULL COMMENT '멤버명',
    `ROLE_CD`          varchar(20)  NOT NULL DEFAULT 'MEMBER' COMMENT '역할코드(OWNER/ADMIN/MEMBER)',
    `MEMBER_STATUS_CD` varchar(20)  NOT NULL DEFAULT 'INVITED' COMMENT '멤버상태코드',
    `IS_MAIN_YN`       varchar(1)   NOT NULL DEFAULT 'N' COMMENT '대표멤버 여부',
    `JOIN_DT`          datetime              DEFAULT NULL COMMENT '가입일시',
    `LEAVE_DT`         datetime              DEFAULT NULL COMMENT '탈퇴일시',
    `USE_YN`           varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`           varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`           datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`           varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`           datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`MEMBER_ID`),
    KEY `IDX_TB_COMPANY_MEMBER_01` (`COMPANY_ID`, `USE_YN`),
    KEY `IDX_TB_COMPANY_MEMBER_02` (`USER_ID`),
    KEY `IDX_TB_COMPANY_MEMBER_03` (`MEMBER_EMAIL`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='기업 멤버정보';

-- 4. 기업 맞춤 설정
-- 4-2. 기업 맞춤 지역
CREATE TABLE `tb_company_custom_setting`
(
    `COMPANY_ID`            bigint      NOT NULL COMMENT '기업ID',
    `BUDGET_FROM_IDX`       int                  DEFAULT NULL COMMENT '예산 시작 인덱스',
    `BUDGET_TO_IDX`         int                  DEFAULT NULL COMMENT '예산 종료 인덱스',
    `BUDGET_MIN_AMT`        decimal(18, 2)       DEFAULT NULL COMMENT '최소예산',
    `BUDGET_MAX_AMT`        decimal(18, 2)       DEFAULT NULL COMMENT '최대예산',
    `ORG_SIZE_CD`           varchar(30)          DEFAULT NULL COMMENT '기관규모코드(SMALL_BIZ/MID_BIZ/LARGE_BIZ)',
    `PARTICIPATION_TYPE_CD` varchar(20)          DEFAULT NULL COMMENT '참여유형코드(SINGLE/JOINT)',
    `KEYWORD_RECOMMEND_YN`  varchar(1)  NOT NULL DEFAULT 'N' COMMENT '키워드추천 사용 여부',
    `BID_NOTICE_MATCH_YN`   varchar(1)  NOT NULL DEFAULT 'Y' COMMENT '공고매칭 사용 여부',
    `PROPOSAL_MATCH_YN`     varchar(1)  NOT NULL DEFAULT 'Y' COMMENT '제안매칭 사용 여부',
    `USE_YN`                varchar(1)  NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`                varchar(50) NOT NULL COMMENT '등록자ID',
    `REG_DT`                datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`                varchar(50)          DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`                datetime             DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`COMPANY_ID`),
    KEY `IDX_TB_COMPANY_CUSTOM_SETTING_01` (`USE_YN`, `ORG_SIZE_CD`, `PARTICIPATION_TYPE_CD`),
    KEY `IDX_TB_COMPANY_CUSTOM_SETTING_02` (`BUDGET_MIN_AMT`, `BUDGET_MAX_AMT`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='기업 맞춤 설정';

-- 4-2. 기업 맞춤 지역
CREATE TABLE `tb_company_custom_region`
(
    `SEQ`        bigint      NOT NULL AUTO_INCREMENT COMMENT '순번',
    `COMPANY_ID` bigint      NOT NULL COMMENT '기업ID',
    `REGION_CD`  varchar(50) NOT NULL COMMENT '지역코드',
    `SORT_ORD`   int         NOT NULL DEFAULT 1 COMMENT '정렬순서',
    `USE_YN`     varchar(1)  NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`     varchar(50) NOT NULL COMMENT '등록자ID',
    `REG_DT`     datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`     varchar(50)          DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`     datetime             DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`SEQ`),
    KEY `IDX_TB_COMPANY_CUSTOM_REGION_01` (`COMPANY_ID`, `USE_YN`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='기업 맞춤 지역';

-- 5. 키워드 사전 / 기업 키워드
-- 5-1. 키워드 마스터
CREATE TABLE `tb_keyword_master`
(
    `KEYWORD_ID`        bigint       NOT NULL AUTO_INCREMENT COMMENT '키워드ID',
    `KEYWORD_NM`        varchar(200) NOT NULL COMMENT '키워드명',
    `KEYWORD_GROUP_CD`  varchar(30)           DEFAULT NULL COMMENT '키워드그룹코드',
    `KEYWORD_TYPE_CD`   varchar(20)  NOT NULL DEFAULT 'SYSTEM' COMMENT '키워드유형코드(SYSTEM/ADMIN/AI_SEED)',
    `PARENT_KEYWORD_ID` bigint                DEFAULT NULL COMMENT '상위키워드ID',
    `DISPLAY_YN`        varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '화면표시 여부',
    `USE_YN`            varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`            varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`            datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`            varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`            datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`KEYWORD_ID`),
    UNIQUE KEY `UK_TB_KEYWORD_MASTER_01` (`KEYWORD_NM`),
    KEY `IDX_TB_KEYWORD_MASTER_01` (`KEYWORD_GROUP_CD`, `DISPLAY_YN`, `USE_YN`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='키워드 마스터';

-- 5-2. 키워드 동의어
CREATE TABLE `tb_keyword_alias`
(
    `ALIAS_ID`   bigint       NOT NULL AUTO_INCREMENT COMMENT '동의어ID',
    `KEYWORD_ID` bigint       NOT NULL COMMENT '키워드ID',
    `ALIAS_NM`   varchar(200) NOT NULL COMMENT '동의어명',
    `USE_YN`     varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`     varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`     datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`     varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`     datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`ALIAS_ID`),
    UNIQUE KEY `UK_TB_KEYWORD_ALIAS_01` (`KEYWORD_ID`, `ALIAS_NM`),
    KEY `IDX_TB_KEYWORD_ALIAS_01` (`ALIAS_NM`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='키워드 동의어';

-- 5-3. 기업 키워드
CREATE TABLE `tb_company_keyword`
(
    `SEQ`            bigint      NOT NULL AUTO_INCREMENT COMMENT '순번',
    `COMPANY_ID`     bigint      NOT NULL COMMENT '기업ID',
    `KEYWORD_ID`     bigint      NOT NULL COMMENT '키워드ID',
    `KEYWORD_SRC_CD` varchar(20) NOT NULL DEFAULT 'MANUAL' COMMENT '키워드출처코드(MANUAL/AI_DOC/ADMIN)',
    `KEYWORD_RAW_NM` varchar(200)         DEFAULT NULL COMMENT '원문키워드',
    `WEIGHT_SCORE`   decimal(8, 2)        DEFAULT NULL COMMENT '가중치점수',
    `SORT_ORD`       int         NOT NULL DEFAULT 1 COMMENT '정렬순서',
    `USE_YN`         varchar(1)  NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`         varchar(50) NOT NULL COMMENT '등록자ID',
    `REG_DT`         datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`         varchar(50)          DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`         datetime             DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`SEQ`),
    UNIQUE KEY `UK_TB_COMPANY_KEYWORD_01` (`COMPANY_ID`, `KEYWORD_ID`, `KEYWORD_SRC_CD`),
    KEY `IDX_TB_COMPANY_KEYWORD_01` (`COMPANY_ID`, `USE_YN`),
    KEY `IDX_TB_COMPANY_KEYWORD_02` (`KEYWORD_ID`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='기업 키워드';

-- 6. 기업 자체 문서함
CREATE TABLE `tb_company_doc`
(
    `DOC_ID`           bigint       NOT NULL AUTO_INCREMENT COMMENT '기업문서ID',
    `COMPANY_ID`       bigint       NOT NULL COMMENT '기업ID',
    `DOC_TITLE`        varchar(300) NOT NULL COMMENT '문서제목',
    `DOC_TYPE_CD`      varchar(30)  NOT NULL COMMENT '문서유형코드(PROPOSAL/PERFORMANCE/INTRO/CERT/ETC)',
    `ORG_FILE_NM`      varchar(255) NOT NULL COMMENT '원본파일명',
    `SOURCE_PATH`      varchar(1000)         DEFAULT NULL COMMENT '원본파일 URL 또는 저장위치',
    `DOC_STATUS_CD`    varchar(20)  NOT NULL DEFAULT 'UPLOADED' COMMENT '문서상태코드(UPLOADED/INDEXED/FAILED/ARCHIVED)',
    `DIFY_SYNC_YN`     varchar(1)   NOT NULL DEFAULT 'N' COMMENT 'Dify 동기화 여부',
    `LAST_SYNC_DT`     datetime              DEFAULT NULL COMMENT '마지막 동기화일시',
    `LAST_ANALYSIS_DT` datetime              DEFAULT NULL COMMENT '마지막 분석일시',
    `DESCRIPTION`      varchar(1000)         DEFAULT NULL COMMENT '설명',
    `USE_YN`           varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`           varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`           datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`           varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`           datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`DOC_ID`),
    KEY `IDX_TB_COMPANY_DOC_01` (`COMPANY_ID`, `USE_YN`),
    KEY `IDX_TB_COMPANY_DOC_02` (`DIFY_SYNC_YN`, `LAST_SYNC_DT`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='기업 자체 문서함';


-- 7. 사용자 알림 설정
CREATE TABLE `tb_user_notice_setting`
(
    `USER_ID`         varchar(50) NOT NULL COMMENT '사용자ID',
    `COMPANY_ID`      bigint      NOT NULL COMMENT '기업ID',
    `EMAIL_NOTICE_YN` varchar(1)  NOT NULL DEFAULT 'Y' COMMENT '이메일 알림 여부',
    `KAKAO_NOTICE_YN` varchar(1)  NOT NULL DEFAULT 'N' COMMENT '카카오 알림 여부',
    `NOTICE_CYCLE_CD` varchar(20) NOT NULL DEFAULT 'REALTIME' COMMENT '알림주기코드',
    `USE_YN`          varchar(1)  NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`          varchar(50) NOT NULL COMMENT '등록자ID',
    `REG_DT`          datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`          varchar(50)          DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`          datetime             DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`USER_ID`, `COMPANY_ID`),
    KEY `IDX_TB_USER_NOTICE_SETTING_01` (`COMPANY_ID`, `USE_YN`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='사용자 공고 알림 설정';


-- 8. 공고 메타데이터
-- 8-1. 공고 마스터
CREATE TABLE `tb_procure_notice`
(
    `NOTICE_ID`        bigint       NOT NULL AUTO_INCREMENT COMMENT '공고ID',
    `BID_NO`           varchar(50)  NOT NULL COMMENT '공고번호',
    `BID_ORD`          varchar(10)  NOT NULL COMMENT '공고차수',
    `BID_KIND`         varchar(100)          DEFAULT NULL COMMENT '공고종류',
    `BID_TITLE`        varchar(500) NOT NULL COMMENT '공고명',
    `ORG_NM`           varchar(200)          DEFAULT NULL COMMENT '기관명',
    `BID_DT`           varchar(20)           DEFAULT NULL COMMENT '공고일시 원문',
    `OPEN_DT`          varchar(20)           DEFAULT NULL COMMENT '개찰일시 원문',
    `BUDGET_AMT`       varchar(50)           DEFAULT NULL COMMENT '예산 원문',
    `AWARD_TYPE_NM`    varchar(200)          DEFAULT NULL COMMENT '낙찰방법',
    `DETAIL_URL`       varchar(1000)         DEFAULT NULL COMMENT '상세URL',
    `NOTICE_STATUS_CD` varchar(20)  NOT NULL DEFAULT 'COLLECTED' COMMENT '공고상태코드',
    `LAST_COLLECT_DT`  datetime              DEFAULT NULL COMMENT '마지막 수집일시',
    `LAST_SYNC_DT`     datetime              DEFAULT NULL COMMENT '마지막 동기화일시',
    `USE_YN`           varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`           varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`           datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`           varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`           datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`NOTICE_ID`),
    UNIQUE KEY `UK_TB_PROCURE_NOTICE_01` (`BID_NO`, `BID_ORD`),
    KEY `IDX_TB_PROCURE_NOTICE_01` (`NOTICE_STATUS_CD`, `LAST_SYNC_DT`),
    KEY `IDX_TB_PROCURE_NOTICE_02` (`ORG_NM`),
    KEY `IDX_TB_PROCURE_NOTICE_03` (`REG_DT`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='조달 공고 메타정보';

-- 8-2. 공고 첨부파일 메타
CREATE TABLE `tb_procure_notice_file`
(
    `NOTICE_FILE_ID` bigint        NOT NULL AUTO_INCREMENT COMMENT '공고첨부파일ID',
    `NOTICE_ID`      bigint        NOT NULL COMMENT '공고ID',
    `FILE_NM`        varchar(255)  NOT NULL COMMENT '첨부파일명',
    `FILE_URL`       varchar(2000) NOT NULL COMMENT '첨부파일URL',
    `FILE_EXT`       varchar(20)            DEFAULT NULL COMMENT '확장자',
    `FILE_TYPE_CD`   varchar(20)   NOT NULL DEFAULT 'UNCLEAR' COMMENT '파일유형(RFP/UNCLEAR/EXCLUDE)',
    `IS_PRIMARY_YN`  varchar(1)    NOT NULL DEFAULT 'N' COMMENT '대표파일 여부',
    `DIFY_SYNC_YN`   varchar(1)    NOT NULL DEFAULT 'N' COMMENT 'Dify 동기화 여부',
    `LAST_SYNC_DT`   datetime               DEFAULT NULL COMMENT '마지막 동기화일시',
    `USE_YN`         varchar(1)    NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`         varchar(50)   NOT NULL COMMENT '등록자ID',
    `REG_DT`         datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`         varchar(50)            DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`         datetime               DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`NOTICE_FILE_ID`),
    KEY `IDX_TB_PROCURE_NOTICE_FILE_01` (`NOTICE_ID`, `USE_YN`),
    KEY `IDX_TB_PROCURE_NOTICE_FILE_02` (`FILE_TYPE_CD`, `IS_PRIMARY_YN`),
    KEY `IDX_TB_PROCURE_NOTICE_FILE_03` (`DIFY_SYNC_YN`, `LAST_SYNC_DT`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='조달 공고 첨부파일 메타';

CREATE TABLE `tb_procure_notice_keyword`
(
    `SEQ`            bigint      NOT NULL AUTO_INCREMENT COMMENT '순번',
    `NOTICE_ID`      bigint      NOT NULL COMMENT '공고ID',
    `KEYWORD_ID`     bigint      NOT NULL COMMENT '키워드ID',
    `KEYWORD_SRC_CD` varchar(20) NOT NULL DEFAULT 'AI' COMMENT '키워드출처코드(AI/RULE/ADMIN)',
    `KEYWORD_RAW_NM` varchar(200)         DEFAULT NULL COMMENT '원문키워드',
    `WEIGHT_SCORE`   decimal(8, 2)        DEFAULT NULL COMMENT '가중치점수',
    `USE_YN`         varchar(1)  NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`         varchar(50) NOT NULL COMMENT '등록자ID',
    `REG_DT`         datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`         varchar(50)          DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`         datetime             DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`SEQ`),
    UNIQUE KEY `UK_TB_PROCURE_NOTICE_KEYWORD_01` (`NOTICE_ID`, `KEYWORD_ID`, `KEYWORD_SRC_CD`),
    KEY `IDX_TB_PROCURE_NOTICE_KEYWORD_01` (`NOTICE_ID`, `USE_YN`),
    KEY `IDX_TB_PROCURE_NOTICE_KEYWORD_02` (`KEYWORD_ID`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='공고 키워드';

-- 9. Dify 연동 메타


-- 9-2. Dify document 매핑
CREATE TABLE `tb_dify_document_map`
(
    `MAP_ID`           bigint       NOT NULL AUTO_INCREMENT COMMENT '매핑ID',
    `DATASET_ID`       bigint       NOT NULL COMMENT '내부 데이터셋ID',
    `SOURCE_TYPE_CD`   varchar(30)  NOT NULL COMMENT '원본유형(COMPANY_DOC/NOTICE_FILE)',
    `SOURCE_PK`        bigint       NOT NULL COMMENT '원본PK',
    `DIFY_DOCUMENT_ID` varchar(100) NOT NULL COMMENT 'Dify document ID',
    `DIFY_DOCUMENT_NM` varchar(255)          DEFAULT NULL COMMENT 'Dify document 명',
    `INDEX_STATUS_CD`  varchar(20)  NOT NULL DEFAULT 'READY' COMMENT '인덱싱상태코드',
    `LAST_SYNC_DT`     datetime              DEFAULT NULL COMMENT '마지막 동기화일시',
    `LAST_ERROR_MSG`   varchar(2000)         DEFAULT NULL COMMENT '마지막 오류메시지',
    `USE_YN`           varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`           varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`           datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`           varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`           datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`MAP_ID`),
    UNIQUE KEY `UK_TB_DIFY_DOCUMENT_MAP_01` (`DATASET_ID`, `SOURCE_TYPE_CD`, `SOURCE_PK`),
    KEY `IDX_TB_DIFY_DOCUMENT_MAP_01` (`DIFY_DOCUMENT_ID`),
    KEY `IDX_TB_DIFY_DOCUMENT_MAP_02` (`INDEX_STATUS_CD`, `LAST_SYNC_DT`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='Dify 문서 매핑';

-- 10. 배치 운영
-- 10-1. 배치 JOB
CREATE TABLE `tb_batch_job`
(
    `JOB_ID`            bigint      NOT NULL AUTO_INCREMENT COMMENT '배치JOB ID',
    `JOB_TYPE_CD`       varchar(30) NOT NULL COMMENT 'JOB유형(NOTICE_COLLECT/NOTICE_INDEX/COMPANY_DOC_INDEX/COMPANY_RECOMMEND)',
    `JOB_STATUS_CD`     varchar(20) NOT NULL DEFAULT 'READY' COMMENT 'JOB상태(READY/RUNNING/SUCCESS/FAIL/PARTIAL_SUCCESS)',
    `REQUEST_SOURCE_CD` varchar(20) NOT NULL DEFAULT 'SCHEDULER' COMMENT '요청출처(USER/ADMIN/SCHEDULER)',
    `REQUEST_USER_ID`   varchar(50)          DEFAULT NULL COMMENT '요청사용자ID',
    `START_DT`          datetime             DEFAULT NULL COMMENT '시작일시',
    `END_DT`            datetime             DEFAULT NULL COMMENT '종료일시',
    `TOTAL_CNT`         int         NOT NULL DEFAULT 0 COMMENT '총건수',
    `SUCCESS_CNT`       int         NOT NULL DEFAULT 0 COMMENT '성공건수',
    `FAIL_CNT`          int         NOT NULL DEFAULT 0 COMMENT '실패건수',
    `PARAM_JSON`        text COMMENT '요청파라미터 JSON',
    `ERROR_MSG`         varchar(2000)        DEFAULT NULL COMMENT '오류메시지',
    `REG_ID`            varchar(50) NOT NULL COMMENT '등록자ID',
    `REG_DT`            datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`            varchar(50)          DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`            datetime             DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`JOB_ID`),
    KEY `IDX_TB_BATCH_JOB_01` (`JOB_TYPE_CD`, `JOB_STATUS_CD`),
    KEY `IDX_TB_BATCH_JOB_02` (`REQUEST_USER_ID`),
    KEY `IDX_TB_BATCH_JOB_03` (`REG_DT`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='배치 JOB';

-- 10-2. 배치 JOB ITEM
CREATE TABLE `tb_batch_job_item`
(
    `JOB_ITEM_ID`       bigint      NOT NULL AUTO_INCREMENT COMMENT '배치JOB ITEM ID',
    `JOB_ID`            bigint      NOT NULL COMMENT '배치JOB ID',
    `TARGET_TYPE_CD`    varchar(30) NOT NULL COMMENT '대상유형(NOTICE/NOTICE_FILE/COMPANY_DOC/COMPANY)',
    `TARGET_PK`         bigint      NOT NULL COMMENT '대상PK',
    `PROCESS_STATUS_CD` varchar(20) NOT NULL DEFAULT 'READY' COMMENT '처리상태',
    `RESULT_MSG`        varchar(2000)        DEFAULT NULL COMMENT '처리결과메시지',
    `START_DT`          datetime             DEFAULT NULL COMMENT '시작일시',
    `END_DT`            datetime             DEFAULT NULL COMMENT '종료일시',
    `REG_ID`            varchar(50) NOT NULL COMMENT '등록자ID',
    `REG_DT`            datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`            varchar(50)          DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`            datetime             DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`JOB_ITEM_ID`),
    KEY `IDX_TB_BATCH_JOB_ITEM_01` (`JOB_ID`, `PROCESS_STATUS_CD`),
    KEY `IDX_TB_BATCH_JOB_ITEM_02` (`TARGET_TYPE_CD`, `TARGET_PK`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='배치 JOB ITEM';

ALTER TABLE TB_COMPANY_INFO
    ADD COLUMN BIZ_CERT_FILE_NM  VARCHAR(255)  DEFAULT NULL COMMENT '사업자등록증 파일명',
    ADD COLUMN BIZ_CERT_FILE_URL VARCHAR(1000) DEFAULT NULL COMMENT '사업자등록증 파일경로';

ALTER TABLE cep.tb_company_info
    CHANGE BIZ_CERT_FILE_URL BIZ_CERT_FILE_PATH varchar(1000) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '사업자등록증 파일경로';


CREATE TABLE `tb_code_master`
(
    `CODE_GROUP_ID` varchar(50)  NOT NULL COMMENT '코드그룹ID',
    `CODE_GROUP_NM` varchar(100) NOT NULL COMMENT '코드그룹명',
    `DESCRIPTION`   varchar(500)          DEFAULT NULL COMMENT '설명',
    `USE_YN`        varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`        varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`        datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`        varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`        datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`CODE_GROUP_ID`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='공통코드 그룹';

CREATE TABLE `tb_code_detail`
(
    `CODE_ID`       bigint       NOT NULL AUTO_INCREMENT COMMENT '코드ID',
    `CODE_GROUP_ID` varchar(50)  NOT NULL COMMENT '코드그룹ID',
    `CODE_VALUE`    varchar(50)  NOT NULL COMMENT '코드값',
    `CODE_NM`       varchar(100) NOT NULL COMMENT '코드명',
    `REF_VALUE1`    varchar(100)          DEFAULT NULL COMMENT '참조값1',
    `REF_VALUE2`    varchar(100)          DEFAULT NULL COMMENT '참조값2',
    `SORT_ORD`      int          NOT NULL DEFAULT 1 COMMENT '정렬순서',
    `USE_YN`        varchar(1)   NOT NULL DEFAULT 'Y' COMMENT '사용여부',
    `REG_ID`        varchar(50)  NOT NULL COMMENT '등록자ID',
    `REG_DT`        datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일자',
    `UPD_ID`        varchar(50)           DEFAULT NULL COMMENT '수정자ID',
    `UPD_DT`        datetime              DEFAULT NULL COMMENT '수정일자',
    PRIMARY KEY (`CODE_ID`),
    UNIQUE KEY `UK_TB_CODE_DETAIL_01` (`CODE_GROUP_ID`, `CODE_VALUE`),
    KEY `IDX_TB_CODE_DETAIL_01` (`CODE_GROUP_ID`, `USE_YN`, `SORT_ORD`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='공통코드 상세';

ALTER TABLE `tb_company_custom_region`
    ADD UNIQUE KEY `UK_TB_COMPANY_CUSTOM_REGION_01` (`COMPANY_ID`, `REGION_CD`);
ALTER TABLE `tb_company_industry`
    ADD UNIQUE KEY `UK_TB_COMPANY_INDUSTRY_01` (`COMPANY_ID`, `INDUSTRY_CD`);
ALTER TABLE `tb_company_item`
    ADD UNIQUE KEY `UK_TB_COMPANY_ITEM_01` (`COMPANY_ID`, `ITEM_CD`);

ALTER TABLE `tb_company_member`
    ADD UNIQUE KEY `UK_TB_COMPANY_MEMBER_04` (`COMPANY_ID`, `USER_ID`);

ALTER TABLE `tb_user_notice_setting`
    ADD COLUMN `TODAY_NOTICE_YN`    varchar(1) NOT NULL DEFAULT 'Y' COMMENT '오늘의 공고 알림 여부' AFTER `KAKAO_NOTICE_YN`,
    ADD COLUMN `DEADLINE_NOTICE_YN` varchar(1) NOT NULL DEFAULT 'Y' COMMENT '마감임박 공고 알림 여부' AFTER `TODAY_NOTICE_YN`,
    ADD COLUMN `REALTIME_NOTICE_YN` varchar(1) NOT NULL DEFAULT 'Y' COMMENT '실시간 공고 알림 여부' AFTER `DEADLINE_NOTICE_YN`;