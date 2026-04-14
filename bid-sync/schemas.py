from pydantic import BaseModel
from typing import Optional, List

class BidExistsRequest(BaseModel):
    bid_ntce_no: str
    bid_ntce_ord: str = "00"

class BidExistsResponse(BaseModel):
    exists: bool
    bid_ntce_no: str

class BidInsertRequest(BaseModel):
    bid_ntce_no: str
    bid_ntce_ord: str = "00"
    bid_ntce_nm: Optional[str] = None
    ntce_instt_nm: Optional[str] = None
    dmnd_instt_nm: Optional[str] = None
    bid_ntce_dt: Optional[str] = None
    openg_dt: Optional[str] = None
    close_dt: Optional[str] = None
    bid_mtd_nm: Optional[str] = None
    cntrct_cnclsn_mtd_nm: Optional[str] = None
    presmpt_prce: Optional[str] = None
    has_rfp: Optional[bool] = False
    rfp_file_url: Optional[str] = None
    raw_json: Optional[str] = None

class BidSyncRequest(BaseModel):
    items: List[dict]  # 나라장터 API 원본 items 그대로

class BidSyncResponse(BaseModel):
    total: int
    inserted: int
    skipped: int