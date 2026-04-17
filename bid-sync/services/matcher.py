import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import and_, text
from sqlalchemy.orm import Session

from models import Bid, BidCompanyMapping
from services.dify_client import retrieve_rag_scores

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 가중치
W_ITEM     = 0.30
W_KEYWORD  = 0.25
W_RFP_RAG  = 0.35
# W_COMPANY_DOC = 0.10  # TODO


def _get_item_codes(company_id: int, db: Session) -> list[str]:
    rows = db.execute(text("""
        SELECT ITEM_CD FROM tb_company_item
        WHERE COMPANY_ID = :cid AND USE_YN = 'Y'
    """), {"cid": company_id}).fetchall()
    return [r[0] for r in rows]


def _get_keywords(company_id: int, db: Session) -> tuple[set[str], list[str]]:
    """
    (정규화된 키워드 set, 원본 키워드 list) 반환.
    정규화: 매칭 비교용 / 원본: RAG 쿼리용
    """
    rows = db.execute(text("""
        SELECT km.KEYWORD_NM
        FROM tb_company_keyword ck
        JOIN tb_keyword_master km ON ck.KEYWORD_ID = km.KEYWORD_ID
        WHERE ck.COMPANY_ID = :cid AND ck.USE_YN = 'Y' AND km.USE_YN = 'Y'
    """), {"cid": company_id}).fetchall()

    alias_rows = db.execute(text("""
        SELECT ka.ALIAS_NM
        FROM tb_company_keyword ck
        JOIN tb_keyword_alias ka ON ck.KEYWORD_ID = ka.KEYWORD_ID
        WHERE ck.COMPANY_ID = :cid AND ck.USE_YN = 'Y' AND ka.USE_YN = 'Y'
    """), {"cid": company_id}).fetchall()

    originals = [r[0] for r in rows if r[0]]
    normalized = {_normalize(r[0]) for r in rows + alias_rows if r[0]}
    return normalized, originals


def _get_settings(company_id: int, db: Session) -> dict:
    row = db.execute(text("""
        SELECT BUDGET_MIN_AMT, BUDGET_MAX_AMT, PARTICIPATION_TYPE_CD
        FROM tb_company_custom_setting
        WHERE COMPANY_ID = :cid AND USE_YN = 'Y'
    """), {"cid": company_id}).fetchone()
    if not row:
        return {}
    return {
        "budget_min": row[0],
        "budget_max": row[1],
        "participation_type_cd": row[2],
    }


def _get_profile_summary(company_id: int, db: Session) -> str:
    """RAG 쿼리에 사용할 기업 프로필 요약"""
    row = db.execute(text("""
        SELECT PROFILE_SUMMARY FROM tb_company_profile
        WHERE COMPANY_ID = :cid AND USE_YN = 'Y'
    """), {"cid": company_id}).fetchone()
    return row[0] if row and row[0] else ""


def _normalize(s: str) -> str:
    return s.replace(" ", "").lower()


def _matches_item_code(bid_clsfctn_no: str | None, item_codes: list[str]) -> bool:
    """전방 일치: 기업 품목코드가 공고 분류번호의 접두사이거나 같으면 매칭"""
    if not bid_clsfctn_no or not item_codes:
        return False
    for item_cd in item_codes:
        if bid_clsfctn_no.startswith(item_cd) or item_cd.startswith(bid_clsfctn_no):
            return True
    return False


def _calc_keyword_score(bid_keywords: list[str], company_keywords: set[str]) -> tuple[list[str], float]:
    """매칭된 키워드 목록과 점수 반환"""
    if not company_keywords or not bid_keywords:
        return [], 0.0

    normalized_bid = [_normalize(k) for k in bid_keywords]
    matched = []
    for ck in company_keywords:
        if any(ck in bk or bk in ck for bk in normalized_bid):
            matched.append(ck)

    if not matched:
        return [], 0.0

    score = min(len(matched) / len(company_keywords), 1.0)
    return matched, score


def _get_active_bids(db: Session, settings: dict, company_id: int | None = None, new_only: bool = False) -> list[Bid]:
    """
    new_only=True: 해당 기업에 아직 매핑되지 않은 신규 공고만 반환 (배치용)
    new_only=False: 전체 활성 공고 반환 (프로필 변경 후 전체 재매칭용)
    """
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    query = db.query(Bid).filter(
        Bid.keyword_status == "DONE",
        (Bid.bid_clse_dt == None) | (Bid.bid_clse_dt == "") | (Bid.bid_clse_dt > now_kst),
    )

    if new_only and company_id is not None:
        matched_sub = (
            db.query(BidCompanyMapping.bid_ntce_no, BidCompanyMapping.bid_ntce_ord)
            .filter(BidCompanyMapping.company_id == company_id)
            .subquery()
        )
        query = query.outerjoin(
            matched_sub,
            and_(
                Bid.bid_ntce_no == matched_sub.c.bid_ntce_no,
                Bid.bid_ntce_ord == matched_sub.c.bid_ntce_ord,
            )
        ).filter(matched_sub.c.bid_ntce_no == None)

    if settings.get("budget_min"):
        query = query.filter(Bid.presmpt_prce >= int(settings["budget_min"]))
    if settings.get("budget_max"):
        query = query.filter(Bid.presmpt_prce <= int(settings["budget_max"]))
    # TODO: participation_type_cd 필터 (cntrct_cnclsn_mtd_nm 매핑 기준 확정 후 추가)
    return query.all()


async def match_company(company_id: int, db: Session, new_only: bool = False) -> dict:
    """
    단일 기업 매칭 실행 후 tb_bids_company_mapping upsert.
    new_only=True: 미매핑 신규 공고만 (배치 스케줄용)
    new_only=False: 전체 활성 공고 재매칭 (프로필 변경 후 온디맨드용)

    매칭 조건: 품목코드 OR 키워드 중 하나 이상 일치 후 RAG 점수 추가
    점수: W_ITEM(0.30) + W_KEYWORD(0.25) + W_RFP_RAG(0.35) = 최대 0.90
    """
    item_codes = _get_item_codes(company_id, db)
    keywords, keywords_raw = _get_keywords(company_id, db)
    settings = _get_settings(company_id, db)
    profile_summary = _get_profile_summary(company_id, db)

    if not item_codes and not keywords:
        logger.info(f"기업 {company_id}: 품목코드/키워드 없음, 스킵")
        return {"company_id": company_id, "matched": 0, "skipped": True}

    bids = _get_active_bids(db, settings, company_id=company_id, new_only=new_only)
    logger.info(f"기업 {company_id}: 활성 공고 {len(bids)}건 대상 매칭 시작")

    # 1단계: 품목코드 OR 키워드 필터링
    candidates = []
    for bid in bids:
        item_matched = _matches_item_code(bid.bid_clsfctn_no, item_codes)
        matched_kws, kw_score = _calc_keyword_score(bid.keywords or [], keywords)
        if not item_matched and not matched_kws:
            continue
        candidates.append((bid, item_matched, matched_kws, kw_score))

    logger.info(f"기업 {company_id}: 1차 필터 후 후보 {len(candidates)}건")

    # 2단계: 후보 대상 Dify RAG 점수 조회
    # 원본 키워드(공백 유지)로 쿼리 — 정규화된 키워드는 임베딩 품질 저하
    rag_query = " ".join(keywords_raw[:10])
    if profile_summary:
        rag_query = f"{profile_summary[:300]} {rag_query}"

    doc_ids = [bid.dify_doc_id for bid, *_ in candidates if bid.dify_doc_id]
    rag_results: dict[str, dict] = {}
    if doc_ids:
        try:
            rag_results = await retrieve_rag_scores(rag_query, doc_ids)
        except Exception as e:
            logger.warning(f"RAG 점수 조회 실패 (무시): {e}")

    # 3단계: 최종 점수 계산 + upsert
    now = datetime.utcnow()
    matched_count = 0

    for bid, item_matched, matched_kws, kw_score in candidates:
        item_score = W_ITEM if item_matched else 0.0
        rag_hit = rag_results.get(bid.dify_doc_id) if bid.dify_doc_id else None
        raw_rag = rag_hit["score"] if rag_hit else 0.0
        # Dify 한국어 유사도는 0.2~0.6 범위 > 0~1로 리스케일 (0.2 이하=0, 0.6 이상=1)
        rag_score = max(0.0, min(1.0, (raw_rag - 0.2) / 0.4))
        score = round(item_score + kw_score * W_KEYWORD + rag_score * W_RFP_RAG, 4)

        reasons = []
        if item_matched:
            reasons.append(f"품목코드({bid.bid_clsfctn_no})")
        if matched_kws:
            reasons.append(f"키워드({', '.join(matched_kws[:5])})")
        if rag_score > 0:
            reasons.append(f"RAG({rag_score:.2f})")
        reason = " + ".join(reasons)

        # match_keywords: {"keywords": [...], "rag": {"score": float, "segment": str}}
        kw_json: dict = {"keywords": matched_kws}
        if rag_hit and rag_hit["score"] > 0:
            kw_json["rag"] = {"score": round(raw_rag, 4), "segment": rag_hit["segment"]}

        existing = db.query(BidCompanyMapping).filter_by(
            company_id=company_id,
            bid_ntce_no=bid.bid_ntce_no,
            bid_ntce_ord=bid.bid_ntce_ord,
        ).first()

        if existing:
            existing.match_score = score
            existing.match_reason = reason[:1000]
            existing.match_keywords = kw_json
            existing.reason_status = "PENDING"
            existing.last_match_dt = now
        else:
            db.add(BidCompanyMapping(
                company_id=company_id,
                bid_ntce_no=bid.bid_ntce_no,
                bid_ntce_ord=bid.bid_ntce_ord,
                match_type_cd="AI",
                match_score=score,
                match_reason=reason[:1000],
                match_keywords=kw_json,
                reason_status="PENDING",
                last_match_dt=now,
            ))

        matched_count += 1

    db.commit()
    logger.info(f"기업 {company_id}: 매칭 완료 {matched_count}건")
    return {"company_id": company_id, "matched": matched_count}