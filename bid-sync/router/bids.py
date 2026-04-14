from sqlalchemy import tuple_

@router.post("/sync", response_model=BidSyncResponse)
def sync_bids(req: BidSyncRequest, db: Session = Depends(get_db)):
    if not req.items:
        return {"total": 0, "inserted": 0, "skipped": 0}

    # 1) 유효한 항목만 필터
    valid_items = [i for i in req.items if i.get("bidNtceNo")]
    skipped = len(req.items) - len(valid_items)

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

        # PRESMPT_PRCE: 문자열 → 정수 변환
        presmpt_prce = None
        try:
            raw_price = item.get("presmptPrce", "")
            presmpt_prce = int(str(raw_price).replace(",", "")) if raw_price else None
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
            has_rfp              = False,
            file_status          = "PENDING",
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

    return {"total": len(req.items), "inserted": len(new_bids), "skipped": skipped}