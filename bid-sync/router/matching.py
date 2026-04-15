import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from locks import matching_lock
from services.matcher import match_company

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