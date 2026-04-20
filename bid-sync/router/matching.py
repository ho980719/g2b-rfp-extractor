import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from locks import matching_lock
from models import BidCompanyMapping, Bid
from sqlalchemy.orm.attributes import flag_modified
from services.matcher import match_company, _get_items, _get_keywords, _calc_keyword_score, _matched_item_codes
from services.dify_client import run_reason_workflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matching", tags=["matching"])


@router.post("/run")
async def run_batch_matching(db: Session = Depends(get_db)):
    """
    활성 기업 전체 대상 공고 매칭 배치 실행.
    BID_NOTICE_MATCH_YN = 'Y' 인 기업만 대상.
    이미 실행 중이면 즉시 반환.
    """
    if matching_lock.locked():
        logger.info("matching/run 이미 실행 중, 스킵")
        return {"skipped": True, "reason": "already running"}

    async with matching_lock:
        rows = db.execute(text("""
            SELECT ci.COMPANY_ID
            FROM tb_company_info ci
            JOIN tb_company_custom_setting cs ON ci.COMPANY_ID = cs.COMPANY_ID
            WHERE ci.USE_YN = 'Y'
              AND ci.COMPANY_STATUS_CD = 'ACTIVE'
              AND cs.BID_NOTICE_MATCH_YN = 'Y'
              AND cs.USE_YN = 'Y'
        """)).fetchall()

        company_ids = [r[0] for r in rows]
        logger.info(f"배치 매칭 대상 기업: {len(company_ids)}개")

        results = []
        for company_id in company_ids:
            result = await match_company(company_id, db, new_only=True)
            results.append(result)

        total_matched = sum(r.get("matched", 0) for r in results)
        return {
            "total_companies": len(company_ids),
            "total_matched": total_matched,
            "results": results,
        }


@router.post("/run/{company_id}")
async def run_company_matching(company_id: int, db: Session = Depends(get_db)):
    """특정 기업 ID 기준 공고 매칭 즉시 실행."""
    result = await match_company(company_id, db)
    return result


@router.post("/refresh-keywords")
async def refresh_keywords(db: Session = Depends(get_db)):
    """
    기존 tb_bids_company_mapping 의 match_keywords.keywords 를 재생성.
    - alias → 원본 키워드명 교정
    - 품목명 + 키워드명 올바르게 재조합
    점수/RAG는 건드리지 않음.
    """
    rows = (
        db.query(BidCompanyMapping, Bid)
        .join(Bid, (BidCompanyMapping.bid_ntce_no == Bid.bid_ntce_no) &
                   (BidCompanyMapping.bid_ntce_ord == Bid.bid_ntce_ord))
        .all()
    )

    updated = 0
    # 기업별 items/keywords 캐싱 (같은 기업 반복 조회 방지)
    items_cache: dict[int, dict] = {}
    keywords_cache: dict[int, dict] = {}

    for mapping, bid in rows:
        cid = mapping.company_id

        if cid not in items_cache:
            items_cache[cid] = _get_items(cid, db)
        if cid not in keywords_cache:
            keywords_cache[cid], _ = _get_keywords(cid, db)

        items = items_cache[cid]
        company_keywords = keywords_cache[cid]

        kw_json = mapping.match_keywords or {}

        # items: 기존 코드 유지, 품목명 재생성
        matched_items = kw_json.get("items", [])
        matched_item_names = [items[code] for code in matched_items if code in items]

        # keywords: 원본 키워드명으로 재매칭
        matched_kws, _ = _calc_keyword_score(bid.keywords or [], company_keywords)

        mapping.match_keywords = {**kw_json, "item_names": matched_item_names, "keywords": matched_item_names + matched_kws}
        mapping.reason_status = "PENDING"
        flag_modified(mapping, "match_keywords")
        updated += 1

    db.commit()
    logger.info(f"match_keywords 재생성 완료: {updated}건")
    return {"updated": updated}


@router.post("/generate-reasons")
async def generate_reasons(limit: int = 20, db: Session = Depends(get_db)):
    """
    reason_status='PENDING' 인 매핑 대상으로 Dify 워크플로우 호출해 추천 이유 생성.
    limit: 1회 처리 건수 (스케쥴링 체인에 추가해서 반복 호출 권장)
    """
    rows = (
        db.query(BidCompanyMapping, Bid)
        .join(Bid, (BidCompanyMapping.bid_ntce_no == Bid.bid_ntce_no) &
                   (BidCompanyMapping.bid_ntce_ord == Bid.bid_ntce_ord))
        .filter(BidCompanyMapping.reason_status == "PENDING")
        .limit(limit)
        .all()
    )

    if not rows:
        return {"processed": 0, "done": 0, "failed": 0}

    done, failed = 0, 0

    for mapping, bid in rows:
        kw_json       = mapping.match_keywords or {}
        matched_items = kw_json.get("item_names", [])
        item_name_set = set(matched_items)
        # keywords 배열에서 item_names 제외 → 순수 키워드 매칭만 추출
        matched_keywords = [k for k in kw_json.get("keywords", []) if k not in item_name_set]
        rag_segment      = kw_json.get("rag", {}).get("segment", "")

        try:
            reason = await run_reason_workflow(
                bid_title        = bid.bid_ntce_nm or "",
                bid_agency       = bid.ntce_instt_nm or "",
                bid_amount       = f"{int(bid.presmpt_prce):,}원" if bid.presmpt_prce else "미정",
                service_type     = bid.srvce_div_nm or "",
                matched_items    = matched_items,
                matched_keywords = matched_keywords,
                rag_segment      = rag_segment,
                match_score      = float(mapping.match_score or 0),
            )
            if reason:
                mapping.match_reason = reason[:1000]
                mapping.reason_status = "DONE"
                done += 1
            else:
                mapping.reason_status = "FAILED"
                failed += 1
        except Exception as e:
            logger.warning(f"추천이유 생성 실패 company={mapping.company_id} bid={mapping.bid_ntce_no}: {e}")
            mapping.reason_status = "FAILED"
            failed += 1

    db.commit()
    logger.info(f"추천이유 생성: {done}건 완료, {failed}건 실패")
    return {"processed": len(rows), "done": done, "failed": failed}