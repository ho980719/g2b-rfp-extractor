import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def get_plan_limits(company_id: int, db: Session) -> dict | None:
    """
    기업의 ACTIVE 구독 플랜 제한값 조회.
    구독 없거나 ACTIVE 아니면 None 반환 → 매칭 스킵.
    NULL = 무제한.
    """
    row = db.execute(text("""
        SELECT p.BID_RECOMMEND_DAY_LIMIT,
               p.PRESPEC_RECOMMEND_DAY_LIMIT,
               p.ALARM_KAKAO_DAY_LIMIT,
               p.AI_SUMMARY_DAY_LIMIT,
               p.AI_SUMMARY_MONTH_LIMIT,
               p.AI_SEARCH_DAY_LIMIT
        FROM tb_subscription s
        JOIN tb_subscription_plan p ON s.PLAN_ID = p.ID
        WHERE s.COMPANY_ID = :cid AND s.STATUS = 'ACTIVE'
        LIMIT 1
    """), {"cid": company_id}).fetchone()

    if not row:
        return None

    return {
        "BID_RECOMMEND":     row[0],
        "PRESPEC_RECOMMEND": row[1],
        "ALARM_KAKAO":       row[2],
        "AI_SUMMARY_DAY":    row[3],
        "AI_SUMMARY_MONTH":  row[4],
        "AI_SEARCH":         row[5],
    }


def get_today_usage(company_id: int, feature_type: str, db: Session) -> int:
    """당일 누적 사용량 조회. 행 없으면 0."""
    row = db.execute(text("""
        SELECT USE_COUNT FROM tb_subscription_usage_daily
        WHERE COMPANY_ID = :cid AND FEATURE_TYPE = :ft AND USE_DT = CURDATE()
    """), {"cid": company_id, "ft": feature_type}).fetchone()
    return row[0] if row else 0


def increment_usage(company_id: int, feature_type: str, amount: int, db: Session) -> None:
    """사용량 일괄 증가 (upsert). amount = 이번 배치에서 추가된 건수."""
    if amount <= 0:
        return
    db.execute(text("""
        INSERT INTO tb_subscription_usage_daily (COMPANY_ID, FEATURE_TYPE, USE_DT, USE_COUNT)
        VALUES (:cid, :ft, CURDATE(), :amt)
        ON DUPLICATE KEY UPDATE USE_COUNT = USE_COUNT + :amt
    """), {"cid": company_id, "ft": feature_type, "amt": amount})