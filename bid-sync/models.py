from sqlalchemy import Column, String, DateTime, Text, Boolean, BigInteger, JSON, Index
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