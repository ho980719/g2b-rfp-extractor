from sqlalchemy import Column, String, DateTime, Text, Boolean, BigInteger, JSON, Index, Numeric, Integer
from sqlalchemy.sql import func
from database import Base


class Bid(Base):
    __tablename__ = "tb_bids"

    # 기본 식별자
    bid_ntce_no          = Column(String(40),  primary_key=True, comment="공고번호")
    bid_ntce_ord         = Column(String(10),  primary_key=True, comment="공고차수")

    # 공고 기본 정보
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
    bid_kind             = Column(String(100), nullable=True,  comment="공고종류")
    srvce_div_nm         = Column(String(100), nullable=True,  comment="서비스구분명 (기술용역 등)")
    is_mock_yn           = Column(String(1),   default="N",    comment="모의공고여부 (공고번호 T로 시작 시 Y)")
    is_urgent_yn         = Column(String(1),   default="N",    comment="긴급공고여부 (ntceKindNm 긴급 포함 시 Y)")
    detail_url           = Column(Text,        nullable=True,  comment="공고 상세링크")

    # RFP 파일 처리
    has_rfp              = Column(Boolean,     default=False,  comment="RFP 포함 여부")
    rfp_file_url         = Column(Text,        nullable=True,  comment="RFP 파일 URL")
    file_urls            = Column(JSON,        nullable=True,  comment="첨부파일 URL 목록")  
    file_status          = Column(
        String(20), default="PENDING", nullable=True,
        comment="파일처리상태 PENDING/PROCESSING/DONE/FAILED/SKIPPED"                   
    )
    file_processed_at    = Column(DateTime,    nullable=True,  comment="파일처리완료일시")   
    file_error_msg       = Column(String(500), nullable=True,  comment="파일처리 실패사유")  

    # AI 추천 관련
    keywords             = Column(JSON,        nullable=True,  comment="추출 키워드 배열")  
    keyword_status       = Column(
        String(20), default="PENDING", nullable=True,
        comment="키워드추출상태 PENDING/DONE/FAILED"                                     
    )
    keyword_extracted_at = Column(DateTime,    nullable=True,  comment="키워드추출일시")    
    dify_doc_id          = Column(String(100), nullable=True,  comment="Dify 지식DB 문서ID") 

    # 메타
    raw_json             = Column(Text,        nullable=True,  comment="원본 JSON")
    created_at           = Column(DateTime, server_default=func.now(), comment="생성일시")
    updated_at           = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="수정일시")

    __table_args__ = (
        Index("idx_bids_bid_ntce_dt",      "bid_ntce_dt"),
        Index("idx_bids_bid_clse_dt",      "bid_clse_dt"),
        Index("idx_bids_has_rfp",          "has_rfp"),
        Index("idx_bids_file_status",      "file_status"),
        Index("idx_bids_keyword_status",   "keyword_status"),
        Index("idx_bids_ntce_instt",       "ntce_instt_nm"),
        Index("idx_bids_clsfctn_no",       "bid_clsfctn_no"),
    )


class PreSpec(Base):
    __tablename__ = "tb_pre_specs"

    # 기본 식별자
    bf_spec_rgst_no      = Column(String(20),   primary_key=True, comment="사전규격등록번호")

    # 공고 기본 정보
    bsns_div_nm          = Column(String(20),   nullable=True,  comment="업무구분명 (물품/용역/공사/외자)")
    ref_no               = Column(String(105),  nullable=True,  comment="참조번호")
    prdct_clsfc_no_nm    = Column(String(200),  nullable=True,  comment="품목/용역분류명 (공고명 역할)")
    order_instt_nm       = Column(String(200),  nullable=True,  comment="발주기관명")
    rl_dminstt_nm        = Column(String(200),  nullable=True,  comment="실수요기관명")
    asign_bdgt_amt       = Column(BigInteger,   nullable=True,  comment="배정예산금액(원)")
    rcpt_dt              = Column(DateTime,     nullable=True,  comment="접수일시")
    opnin_rgst_clse_dt   = Column(DateTime,     nullable=True,  comment="의견등록마감일시 (입찰마감 역할)")
    ofcl_tel_no          = Column(String(25),   nullable=True,  comment="담당자전화번호")
    ofcl_nm              = Column(String(35),   nullable=True,  comment="담당자명")
    sw_biz_obj_yn        = Column(String(1),    default="N",    comment="SW사업여부 (Y/N)")
    dlvr_tmlmt_dt        = Column(DateTime,     nullable=True,  comment="납품기한일시")
    dlvr_daynum          = Column(Integer,      nullable=True,  comment="납품일수")

    # 파일 (규격문서 최대 5개)
    spec_doc_file_urls   = Column(JSON,         nullable=True,  comment="규격문서파일 URL 목록 (최대 5개)")
    has_spec_doc         = Column(Boolean,      default=False,  comment="규격서 보유 여부")
    prdct_dtl_list       = Column(String(4000), nullable=True,  comment="품목상세목록 원본 ([번호^코드^품목명],...)")

    # 연관 정보
    bid_ntce_no_list     = Column(String(1000), nullable=True,  comment="연관 입찰공고번호 목록 (콤마 구분)")
    rgst_dt              = Column(DateTime,     nullable=True,  comment="등록일시")
    chg_dt               = Column(DateTime,     nullable=True,  comment="변경일시")

    # 파일 처리
    file_status          = Column(
        String(20), default="PENDING", nullable=True,
        comment="파일처리상태 PENDING/PROCESSING/DONE/FAILED/SKIPPED"
    )
    file_processed_at    = Column(DateTime,     nullable=True,  comment="파일처리완료일시")
    file_error_msg       = Column(String(500),  nullable=True,  comment="파일처리실패사유")

    # AI 추천 관련
    keywords             = Column(JSON,         nullable=True,  comment="추출 키워드 배열")
    keyword_status       = Column(
        String(20), default="PENDING", nullable=True,
        comment="키워드추출상태 PENDING/DONE/FAILED"
    )
    keyword_extracted_at = Column(DateTime,     nullable=True,  comment="키워드추출완료일시")
    dify_doc_id          = Column(String(100),  nullable=True,  comment="Dify 지식DB 문서ID")

    # AI 요약 (UI: AI 요약 버튼)
    ai_summary           = Column(Text,         nullable=True,  comment="AI 요약문")

    # 메타
    raw_json             = Column(Text,         nullable=True,  comment="원본 JSON")
    created_at           = Column(DateTime, server_default=func.now(), comment="생성일시")
    updated_at           = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="수정일시")

    __table_args__ = (
        Index("idx_pre_specs_rcpt_dt",        "rcpt_dt"),
        Index("idx_pre_specs_opnin_clse_dt",  "opnin_rgst_clse_dt"),
        Index("idx_pre_specs_file_status",    "file_status"),
        Index("idx_pre_specs_keyword_status", "keyword_status"),
        Index("idx_pre_specs_order_instt",    "order_instt_nm"),
        Index("idx_pre_specs_bsns_div_nm",    "bsns_div_nm"),
        Index("idx_pre_specs_sw_biz_obj_yn",  "sw_biz_obj_yn"),
    )


class PreSpecCompanyMapping(Base):
    __tablename__ = "tb_pre_specs_company_mapping"

    company_id       = Column(BigInteger,    primary_key=True, comment="기업ID")
    bf_spec_rgst_no  = Column(String(40),    primary_key=True, comment="사전규격등록번호")

    match_type_cd    = Column(String(20),    default="AI",      comment="매칭유형 (AI/MANUAL)")
    match_score      = Column(Numeric(5, 4), nullable=True,      comment="매칭점수 (0.0000~1.0000)")
    match_detail     = Column(String(1000),  nullable=True,      comment="매칭 상세 (품목코드/키워드/RAG 등 가시적 확인용)")
    match_reason     = Column(String(1000),  nullable=True,      comment="AI 추천이유 (LLM 생성)")
    match_keywords   = Column(JSON,          nullable=True,      comment="매칭 키워드 (items/item_names/keywords/rag)")
    reason_status    = Column(String(20),    default="PENDING",  comment="추천이유 생성상태 PENDING/DONE/FAILED")
    bookmark_yn      = Column(String(1),     default="N",        comment="북마크 여부")
    last_match_dt    = Column(DateTime,      nullable=True,      comment="마지막 매칭일시")
    created_at       = Column(DateTime,      server_default=func.now())
    updated_at       = Column(DateTime,      onupdate=func.now())

    __table_args__ = (
        Index("idx_pre_specs_mapping_01", "company_id", "bookmark_yn"),
        Index("idx_pre_specs_mapping_02", "bf_spec_rgst_no"),
        Index("idx_pre_specs_mapping_03", "match_type_cd", "last_match_dt"),
        Index("idx_pre_specs_mapping_04", "reason_status"),
    )


class BidCompanyMapping(Base):
    __tablename__ = "tb_bids_company_mapping"

    company_id     = Column(BigInteger,    primary_key=True, comment="기업ID")
    bid_ntce_no    = Column(String(40),    primary_key=True, comment="공고번호")
    bid_ntce_ord   = Column(String(10),    primary_key=True, comment="공고차수")

    match_type_cd  = Column(String(20),    default="AI",     comment="매칭유형 (AI/MANUAL)")
    match_score    = Column(Numeric(5, 4), nullable=True,     comment="매칭점수 (0.0000~1.0000)")
    match_detail   = Column(String(1000),  nullable=True,     comment="매칭 상세 (품목코드/키워드/RAG 등 가시적 확인용)")
    match_reason   = Column(String(1000),  nullable=True,     comment="AI 추천이유 (LLM 생성)")
    match_keywords = Column(JSON,          nullable=True,     comment="매칭 키워드 배열")
    reason_status  = Column(String(20),    default="PENDING", comment="추천이유 생성상태 PENDING/DONE/FAILED")
    bookmark_yn    = Column(String(1),     default="N",      comment="북마크 여부")
    last_match_dt  = Column(DateTime,      nullable=True,     comment="마지막 매칭일시")
    created_at     = Column(DateTime,      server_default=func.now())
    updated_at     = Column(DateTime,      onupdate=func.now())