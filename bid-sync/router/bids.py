import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import tuple_

from database import get_db
from models import Bid
from schemas import BidSyncResponse
from services.bid_classifier import classify_bid
from services.g2b_client import fetch_bids

router = APIRouter(prefix="/bids", tags=["bids"])


@router.post("/sync", response_model=BidSyncResponse)
async def sync_bids(db: Session = Depends(get_db)):
    items = await fetch_bids()

    if not items:
        return {"total": 0, "inserted": 0, "skipped": 0}

    # 1) 유효한 항목만 필터
    valid_items = [i for i in items if i.get("bidNtceNo")]
    skipped = len(items) - len(valid_items)

    # 2) 기존 공고 일괄 조회 (N+1 제거)
    keys = {(i["bidNtceNo"], i.get("bidNtceOrd", "00")) for i in valid_items}
    existing_keys = {
        (r.bid_ntce_no, r.bid_ntce_ord)
        for r in db.query(Bid.bid_ntce_no, Bid.bid_ntce_ord).filter(
            tuple_(Bid.bid_ntce_no, Bid.bid_ntce_ord).in_(keys)
        ).all()
    }

    # 3) 신규만 추출
    new_bids = []
    for item in valid_items:
        key = (item["bidNtceNo"], item.get("bidNtceOrd", "00"))
        if key in existing_keys:
            skipped += 1
            continue

        classified = classify_bid(item)
        if classified is None:  # 취소/낙찰/유찰 공고
            skipped += 1
            continue

        presmpt_prce = None
        try:
            raw = item.get("presmptPrce") or item.get("asignBdgtAmt") or ""
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
            bid_clsfctn_no       = item.get("pubPrcrmntClsfcNo") or item.get("bidClsfctnNo"),
            bid_kind             = item.get("ntceKindNm"),
            srvce_div_nm         = item.get("srvceDivNm"),
            is_mock_yn           = "Y" if item["bidNtceNo"].startswith("T") else "N",
            is_urgent_yn         = "Y" if "긴급" in (item.get("bidNtceNm") or "") else "N",
            detail_url           = item.get("bidNtceDtlUrl"),
            has_rfp              = classified["has_rfp"],
            rfp_file_url         = classified["rfp_url"],
            file_urls            = classified["file_urls"],
            file_status          = "PENDING" if classified["has_rfp"] else "SKIPPED",
            keyword_status       = "PENDING",
            raw_json             = json.dumps(item, ensure_ascii=False),
        ))

    # 4) bulk insert + rollback 보장
    try:
        db.bulk_save_objects(new_bids)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"total": len(items), "inserted": len(new_bids), "skipped": skipped}
