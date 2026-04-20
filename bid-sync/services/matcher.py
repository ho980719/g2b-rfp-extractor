import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import and_, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from models import Bid, BidCompanyMapping
from services.dify_client import retrieve_rag_scores

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 가중치
W_ITEM     = 0.30
W_KEYWORD  = 0.25
W_RFP_RAG  = 0.35
# W_COMPANY_DOC = 0.10  # TODO


def _get_items(company_id: int, db: Session) -> dict[str, str]:
    """품목코드 → 품목명 매핑 반환 {code: name}"""
    rows = db.execute(text("""
        SELECT ITEM_CD, ITEM_NM FROM tb_company_item
        WHERE COMPANY_ID = :cid AND USE_YN = 'Y'
    """), {"cid": company_id}).fetchall()
    return {r[0]: r[1] for r in rows}


def _get_keywords(company_id: int, db: Session) -> tuple[dict[str, str], list[str]]:
    """
    ({normalized: original_keyword_nm}, 원본 키워드 list) 반환.
    - normalized_to_original: 매칭 비교용 (alias 포함, 매칭 시 원본명으로 역조회)
    - originals: RAG 쿼리용 (키워드명만, 공백 유지)
    """
    rows = db.execute(text("""
        SELECT km.KEYWORD_NM
        FROM tb_company_keyword ck
        JOIN tb_keyword_master km ON ck.KEYWORD_ID = km.KEYWORD_ID
        WHERE ck.COMPANY_ID = :cid AND ck.USE_YN = 'Y' AND km.USE_YN = 'Y'
    """), {"cid": company_id}).fetchall()

    alias_rows = db.execute(text("""
        SELECT ka.ALIAS_NM, km.KEYWORD_NM
        FROM tb_company_keyword ck
        JOIN tb_keyword_master km ON ck.KEYWORD_ID = km.KEYWORD_ID
        JOIN tb_keyword_alias ka ON ck.KEYWORD_ID = ka.KEYWORD_ID
        WHERE ck.COMPANY_ID = :cid AND ck.USE_YN = 'Y' AND ka.USE_YN = 'Y'
    """), {"cid": company_id}).fetchall()

    originals = [r[0] for r in rows if r[0]]

    # normalized → 원본 키워드명 매핑 (alias도 원본 키워드명으로 역조회 가능하게)
    normalized_to_original: dict[str, str] = {}
    for r in rows:
        if r[0]:
            normalized_to_original[_normalize(r[0])] = r[0]
    for alias_nm, keyword_nm in alias_rows:
        if alias_nm:
            normalized_to_original[_normalize(alias_nm)] = keyword_nm

    return normalized_to_original, originals


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


def _matched_item_codes(bid_clsfctn_no: str | None, item_codes: list[str]) -> list[str]:
    """전방 일치: 매칭된 품목코드 목록 반환 (빈 리스트 = 미매칭)"""
    if not bid_clsfctn_no or not item_codes:
        return []
    return [
        item_cd for item_cd in item_codes
        if bid_clsfctn_no.startswith(item_cd) or item_cd.startswith(bid_clsfctn_no)
    ]


def _calc_keyword_score(bid_keywords: list[str], company_keywords: dict[str, str]) -> tuple[list[str], float]:
    """
    매칭된 원본 키워드명 목록과 점수 반환.
    company_keywords: {normalized: original_nm} — alias 포함
    """
    if not company_keywords or not bid_keywords:
        return [], 0.0

    normalized_bid = [_normalize(k) for k in bid_keywords]
    matched_originals: set[str] = set()
    for norm_ck, original_nm in company_keywords.items():
        if any(norm_ck in bk or bk in norm_ck for bk in normalized_bid):
            matched_originals.add(original_nm)  # alias여도 원본 키워드명으로 저장

    if not matched_originals:
        return [], 0.0

    unique_keyword_count = len(set(company_keywords.values()))
    score = min(len(matched_originals) / unique_keyword_count, 1.0)
    return list(matched_originals), score


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
    items = _get_items(company_id, db)
    item_codes = list(items.keys())
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
        matched_items = _matched_item_codes(bid.bid_clsfctn_no, item_codes)
        matched_kws, kw_score = _calc_keyword_score(bid.keywords or [], keywords)
        if not matched_items and not matched_kws:
            continue
        candidates.append((bid, matched_items, matched_kws, kw_score))

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
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    matched_count = 0

    for bid, matched_items, matched_kws, kw_score in candidates:
        item_score = W_ITEM if matched_items else 0.0
        rag_hit = rag_results.get(bid.dify_doc_id) if bid.dify_doc_id else None
        raw_rag = rag_hit["score"] if rag_hit else 0.0
        # Dify 한국어 유사도는 0.2~0.6 범위 > 0~1로 리스케일 (0.2 이하=0, 0.6 이상=1)
        rag_score = max(0.0, min(1.0, (raw_rag - 0.2) / 0.4))
        score = round(item_score + kw_score * W_KEYWORD + rag_score * W_RFP_RAG, 4)

        reasons = []
        if matched_items:
            reasons.append(f"품목코드({bid.bid_clsfctn_no})")
        if matched_kws:
            reasons.append(f"키워드({', '.join(matched_kws[:5])})")
        if rag_score > 0:
            reasons.append(f"RAG({rag_score:.2f})")
        reason = " + ".join(reasons)

        # 매칭된 품목코드 → 품목명 변환 후 keywords 배열에 합산
        matched_item_names = [items[code] for code in matched_items if code in items]

        # match_keywords: {"items": [...], "item_names": [...], "keywords": [...], "rag": {...}}
        kw_json: dict = {
            "items":      matched_items,
            "item_names": matched_item_names,
            "keywords":   matched_item_names + matched_kws,
        }
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
            existing.last_match_dt = now_kst
            flag_modified(existing, "match_keywords")
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
                last_match_dt=now_kst,
            ))

        matched_count += 1

    db.commit()
    logger.info(f"기업 {company_id}: 매칭 완료 {matched_count}건")
    return {"company_id": company_id, "matched": matched_count}