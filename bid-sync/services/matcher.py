import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from models import Bid, BidCompanyMapping, PreSpec, PreSpecCompanyMapping
from services.dify_client import retrieve_rag_scores, retrieve_pre_spec_rag_scores
from services.usage_limiter import get_plan_limits, get_today_usage, increment_usage

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 가중치 (합 = 1.0)
W_ITEM     = 0.40
W_KEYWORD  = 0.35
W_PROFILE  = 0.10
W_RFP_RAG  = 0.15


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
    import json
    row = db.execute(text("""
        SELECT BUDGET_BUCKET_JSON, PARTICIPATION_TYPE_CD
        FROM tb_company_custom_setting
        WHERE COMPANY_ID = :cid AND USE_YN = 'Y'
    """), {"cid": company_id}).fetchone()
    if not row:
        return {}

    budget_buckets: list[dict] = []
    if row[0]:
        try:
            for b in json.loads(row[0]):
                min_amt = int(b["BUDGET_MIN_AMT"]) if b.get("BUDGET_MIN_AMT") else None
                max_amt = int(b["BUDGET_MAX_AMT"]) if b.get("BUDGET_MAX_AMT") else None
                budget_buckets.append({"min": min_amt, "max": max_amt})
        except Exception:
            pass

    return {
        "budget_buckets": budget_buckets,
        "participation_type_cd": row[1],
    }


def _get_profile_summary(company_id: int, db: Session) -> str:
    """RAG 쿼리에 사용할 기업 프로필 요약"""
    row = db.execute(text("""
        SELECT PROFILE_SUMMARY FROM tb_company_profile
        WHERE COMPANY_ID = :cid AND USE_YN = 'Y'
    """), {"cid": company_id}).fetchone()
    return row[0] if row and row[0] else ""


def _get_profile_keywords(company_id: int, db: Session) -> list[str]:
    """
    tb_company_profile에서 프로필 키워드 파싱.
    - BUSINESS_AREA: 쉼표 구분 모든 토큰
    - SOLUTION_TECH_AREA: ≤20자 토큰만 (설명 문장 필터링)
    """
    row = db.execute(text("""
        SELECT BUSINESS_AREA, SOLUTION_TECH_AREA FROM tb_company_profile
        WHERE COMPANY_ID = :cid AND USE_YN = 'Y'
    """), {"cid": company_id}).fetchone()
    if not row:
        return []

    keywords: list[str] = []
    if row[0]:
        for token in row[0].split(","):
            token = token.strip()
            if token:
                keywords.append(token)
    if row[1]:
        for token in row[1].split(","):
            token = token.strip()
            if token and len(token) <= 20:
                keywords.append(token)

    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


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


def _calc_keyword_score(
    bid_keywords: list[str],
    company_keywords: dict[str, str],
    bid_ntce_nm: str = "",
) -> tuple[list[str], float]:
    """
    매칭된 원본 키워드명 목록과 점수 반환.
    company_keywords: {normalized: original_nm} — alias 포함
    bid_ntce_nm: LLM 키워드가 부실할 때 공고명 토큰 단위 fallback으로 사용
    """
    if not company_keywords:
        return [], 0.0

    # LLM 추출 키워드 정규화
    normalized_bid = [_normalize(k) for k in bid_keywords]
    # 공고명을 공백 기준 토큰으로 분리해 각각 정규화 (양방향 비교용)
    title_tokens = [_normalize(t) for t in bid_ntce_nm.split() if t.strip()] if bid_ntce_nm else []

    matched_originals: set[str] = set()
    for norm_ck, original_nm in company_keywords.items():
        # 1순위: LLM 추출 키워드와 양방향 부분 일치
        if normalized_bid and any(norm_ck in bk or bk in norm_ck for bk in normalized_bid):
            matched_originals.add(original_nm)
        # 2순위: 공고명 토큰별 양방향 비교 (기존: 전체 문자열 단방향)
        #   - norm_ck in token: "교통" in "교통체계" → 토큰 안에 키워드 포함
        #   - token in norm_ck: "교통" in "지능교통시스템" → 키워드 안에 토큰 포함
        elif title_tokens and any(norm_ck in t or t in norm_ck for t in title_tokens if len(t) >= 2):
            matched_originals.add(original_nm)

    if not matched_originals:
        return [], 0.0

    unique_keyword_count = len(set(company_keywords.values()))
    score = min(len(matched_originals) / unique_keyword_count, 1.0)
    return list(matched_originals), score


def _calc_profile_keyword_score(
    bid_keywords: list[str],
    bid_title: str,
    profile_keywords: list[str],
) -> tuple[list[str], float]:
    """
    프로필 키워드(BUSINESS_AREA + SOLUTION_TECH_AREA)와 공고 키워드/공고명 매칭.
    반환: (matched_keywords, score 0~1)
    """
    if not profile_keywords:
        return [], 0.0

    normalized_bid = [_normalize(k) for k in bid_keywords]
    title_tokens = [_normalize(t) for t in bid_title.split() if t.strip()] if bid_title else []

    matched: set[str] = set()
    for pk in profile_keywords:
        norm_pk = _normalize(pk)
        if normalized_bid and any(norm_pk in bk or bk in norm_pk for bk in normalized_bid):
            matched.add(pk)
        elif title_tokens and any(norm_pk in t or t in norm_pk for t in title_tokens if len(t) >= 2):
            matched.add(pk)

    if not matched:
        return [], 0.0

    score = min(len(matched) / len(profile_keywords), 1.0)
    return list(matched), score


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

    buckets = settings.get("budget_buckets") or []
    if buckets:
        bucket_conditions = []
        for b in buckets:
            conds = []
            if b["min"] is not None:
                conds.append(Bid.presmpt_prce >= b["min"])
            if b["max"] is not None:
                conds.append(Bid.presmpt_prce < b["max"])
            if conds:
                bucket_conditions.append(and_(*conds))
        if bucket_conditions:
            query = query.filter(or_(*bucket_conditions))
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
    # 구독 플랜 확인 — 구독 없으면 매칭 스킵
    limits = get_plan_limits(company_id, db)
    if limits is None:
        logger.info(f"기업 {company_id}: 활성 구독 없음, 스킵")
        return {"company_id": company_id, "matched": 0, "skipped": True, "reason": "no_subscription"}

    bid_recommend_limit = limits["BID_RECOMMEND"]  # None = 무제한
    today_usage = get_today_usage(company_id, "BID_RECOMMEND", db) if bid_recommend_limit is not None else 0

    if bid_recommend_limit is not None and today_usage >= bid_recommend_limit:
        logger.info(f"기업 {company_id}: BID_RECOMMEND 일 한도 초과 ({today_usage}/{bid_recommend_limit}), 스킵")
        return {"company_id": company_id, "matched": 0, "skipped": True, "reason": "limit_exceeded"}

    items = _get_items(company_id, db)
    item_codes = list(items.keys())
    keywords, keywords_raw = _get_keywords(company_id, db)
    settings = _get_settings(company_id, db)
    profile_summary = _get_profile_summary(company_id, db)
    profile_kws = _get_profile_keywords(company_id, db)

    if not item_codes and not keywords and not profile_kws:
        logger.info(f"기업 {company_id}: 품목코드/키워드 없음, 스킵")
        return {"company_id": company_id, "matched": 0, "skipped": True, "reason": "no_items_keywords"}

    bids = _get_active_bids(db, settings, company_id=company_id, new_only=new_only)
    logger.info(f"기업 {company_id}: 활성 공고 {len(bids)}건 대상 매칭 시작")

    # 1단계: 품목코드 OR 키워드 OR 프로필 키워드 필터링
    candidates = []
    for bid in bids:
        matched_items = _matched_item_codes(bid.bid_clsfctn_no, item_codes)
        matched_kws, kw_score = _calc_keyword_score(bid.keywords or [], keywords, bid.bid_ntce_nm or "")
        matched_profile_kws, profile_score = _calc_profile_keyword_score(
            bid.keywords or [], bid.bid_ntce_nm or "", profile_kws
        )
        if not matched_items and not matched_kws and not matched_profile_kws:
            continue
        candidates.append((bid, matched_items, matched_kws, kw_score, matched_profile_kws, profile_score))

    logger.info(f"기업 {company_id}: 1차 필터 후 후보 {len(candidates)}건")

    # 2단계: 후보 대상 Dify RAG 점수 조회
    rag_query = " ".join(keywords_raw[:10] + profile_kws[:5])
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
    new_recommend_count = 0  # 신규 추천 건수 (기존 업데이트 제외)

    for bid, matched_items, matched_kws, kw_score, matched_profile_kws, profile_score in candidates:
        item_score = W_ITEM if matched_items else 0.0
        rag_hit = rag_results.get(bid.dify_doc_id) if bid.dify_doc_id else None
        raw_rag = rag_hit["score"] if rag_hit else 0.0
        # Dify 한국어 유사도는 0.2~0.6 범위 > 0~1로 리스케일 (0.2 이하=0, 0.6 이상=1)
        rag_score = max(0.0, min(1.0, (raw_rag - 0.2) / 0.4))
        score = round(
            item_score + kw_score * W_KEYWORD + profile_score * W_PROFILE + rag_score * W_RFP_RAG, 4
        )

        reasons = []
        if matched_items:
            reasons.append(f"품목코드({bid.bid_clsfctn_no})")
        if matched_kws:
            reasons.append(f"키워드({', '.join(matched_kws[:5])})")
        if matched_profile_kws:
            reasons.append(f"프로필({', '.join(matched_profile_kws[:3])})")
        if rag_score > 0:
            reasons.append(f"RAG({rag_score:.2f})")
        reason = " + ".join(reasons)

        # 매칭된 품목코드 → 품목명 변환 후 keywords 배열에 합산
        matched_item_names = [items[code] for code in matched_items if code in items]

        # match_keywords: {"items": [...], "item_names": [...], "keywords": [...], "profile_keywords": [...], "rag": {...}}
        kw_json: dict = {
            "items":            matched_items,
            "item_names":       matched_item_names,
            "keywords":         matched_item_names + matched_kws,
            "profile_keywords": matched_profile_kws,
        }
        if rag_hit and rag_hit["score"] > 0:
            kw_json["rag"] = {"score": round(raw_rag, 4), "segment": rag_hit["segment"]}

        existing = db.query(BidCompanyMapping).filter_by(
            company_id=company_id,
            bid_ntce_no=bid.bid_ntce_no,
            bid_ntce_ord=bid.bid_ntce_ord,
        ).first()

        # 40% 미만은 저장 제외 (기존 레코드 있으면 삭제)
        if score < 0.40:
            if existing:
                db.delete(existing)
            continue

        # 신규 추천 시 일 한도 체크 (기존 매핑 업데이트는 한도 차감 없음)
        if not existing:
            if bid_recommend_limit is not None and today_usage + new_recommend_count >= bid_recommend_limit:
                logger.info(f"기업 {company_id}: BID_RECOMMEND 일 한도 도달 ({bid_recommend_limit}건), 이후 신규 추천 중단")
                continue
            new_recommend_count += 1

        if existing:
            existing.match_score = score
            existing.match_detail = reason[:1000]
            existing.match_reason = None
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
                match_detail=reason[:1000],
                match_keywords=kw_json,
                reason_status="PENDING",
                last_match_dt=now_kst,
            ))

        matched_count += 1

    # 신규 추천 건수만큼 사용량 증가
    increment_usage(company_id, "BID_RECOMMEND", new_recommend_count, db)

    db.commit()
    logger.info(f"기업 {company_id}: 매칭 완료 {matched_count}건 (신규 {new_recommend_count}건 추천 카운트)")
    return {"company_id": company_id, "matched": matched_count}


def _parse_prdct_dtl_list(prdct_dtl_list: str | None) -> dict[str, str]:
    """
    '[1^4321150102^컴퓨터서비스],[2^4321150901^자동화컴퓨터]' 형식 파싱.
    반환: {품목코드: 품목명}
    """
    if not prdct_dtl_list:
        return {}
    result = {}
    # 대괄호 안 내용 추출
    import re
    for match in re.finditer(r'\[([^\]]+)\]', prdct_dtl_list):
        parts = match.group(1).split("^")
        if len(parts) >= 3:
            code = parts[1].strip()
            name = parts[2].strip()
            if code:
                result[code] = name
    return result


def _get_active_pre_specs(db: Session, settings: dict, company_id: int | None = None, new_only: bool = False) -> list[PreSpec]:
    """
    매칭 대상 사전규격 조회.
    - keyword_status IN (DONE, FAILED) — FAILED도 공고명 fallback 매칭 가능
    - opnin_rgst_clse_dt 미래 또는 NULL (아직 의견 접수 가능)
    """
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    query = db.query(PreSpec).filter(
        PreSpec.keyword_status.in_(["DONE", "FAILED"]),
        or_(PreSpec.opnin_rgst_clse_dt == None, PreSpec.opnin_rgst_clse_dt > now_kst),
    )

    if new_only and company_id is not None:
        matched_sub = (
            db.query(PreSpecCompanyMapping.bf_spec_rgst_no)
            .filter(PreSpecCompanyMapping.company_id == company_id)
            .subquery()
        )
        query = query.outerjoin(
            matched_sub,
            PreSpec.bf_spec_rgst_no == matched_sub.c.bf_spec_rgst_no,
        ).filter(matched_sub.c.bf_spec_rgst_no == None)

    buckets = settings.get("budget_buckets") or []
    if buckets:
        bucket_conditions = []
        for b in buckets:
            conds = []
            if b["min"] is not None:
                conds.append(PreSpec.asign_bdgt_amt >= b["min"])
            if b["max"] is not None:
                conds.append(PreSpec.asign_bdgt_amt < b["max"])
            if conds:
                bucket_conditions.append(and_(*conds))
        if bucket_conditions:
            query = query.filter(or_(*bucket_conditions))

    return query.all()


async def match_company_pre_spec(company_id: int, db: Session, new_only: bool = False) -> dict:
    """
    단일 기업 기준 사전규격 매칭 실행 후 tb_pre_specs_company_mapping upsert.
    기존 match_company()와 동일한 가중치/임계값 적용.
    """
    limits = get_plan_limits(company_id, db)
    if limits is None:
        logger.info(f"기업 {company_id}: 활성 구독 없음 (사전규격), 스킵")
        return {"company_id": company_id, "matched": 0, "skipped": True, "reason": "no_subscription"}

    prespec_limit = limits.get("PRESPEC_RECOMMEND")  # None = 무제한
    today_usage = get_today_usage(company_id, "PRESPEC_RECOMMEND", db) if prespec_limit is not None else 0

    if prespec_limit is not None and today_usage >= prespec_limit:
        logger.info(f"기업 {company_id}: PRESPEC_RECOMMEND 일 한도 초과 ({today_usage}/{prespec_limit}), 스킵")
        return {"company_id": company_id, "matched": 0, "skipped": True, "reason": "limit_exceeded"}

    items = _get_items(company_id, db)
    item_codes = list(items.keys())
    keywords, keywords_raw = _get_keywords(company_id, db)
    settings = _get_settings(company_id, db)
    profile_summary = _get_profile_summary(company_id, db)
    profile_kws = _get_profile_keywords(company_id, db)

    if not item_codes and not keywords and not profile_kws:
        logger.info(f"기업 {company_id}: 품목코드/키워드 없음 (사전규격), 스킵")
        return {"company_id": company_id, "matched": 0, "skipped": True, "reason": "no_items_keywords"}

    pre_specs = _get_active_pre_specs(db, settings, company_id=company_id, new_only=new_only)
    logger.info(f"기업 {company_id}: 활성 사전규격 {len(pre_specs)}건 대상 매칭 시작")

    # 1단계: 품목코드 OR 키워드 OR 프로필 키워드 필터링
    candidates = []
    for ps in pre_specs:
        ps_items = _parse_prdct_dtl_list(ps.prdct_dtl_list)
        ps_item_codes = list(ps_items.keys())

        # 사전규격 품목코드 매칭 (각 품목코드에 대해 전방 일치)
        matched_items = []
        for ps_code in ps_item_codes:
            matched = _matched_item_codes(ps_code, item_codes)
            matched_items.extend(matched)
        matched_items = list(set(matched_items))

        matched_kws, kw_score = _calc_keyword_score(
            ps.keywords or [],
            keywords,
            ps.prdct_clsfc_no_nm or "",
        )
        matched_profile_kws, profile_score = _calc_profile_keyword_score(
            ps.keywords or [], ps.prdct_clsfc_no_nm or "", profile_kws
        )

        if not matched_items and not matched_kws and not matched_profile_kws:
            continue
        candidates.append((ps, ps_items, matched_items, matched_kws, kw_score, matched_profile_kws, profile_score))

    logger.info(f"기업 {company_id}: 사전규격 1차 필터 후 후보 {len(candidates)}건")

    # 2단계: 후보 대상 Dify RAG 점수 조회
    rag_query = " ".join(keywords_raw[:10] + profile_kws[:5])
    if profile_summary:
        rag_query = f"{profile_summary[:300]} {rag_query}"

    doc_ids = [ps.dify_doc_id for ps, *_ in candidates if ps.dify_doc_id]
    rag_results: dict[str, dict] = {}
    if doc_ids:
        try:
            rag_results = await retrieve_pre_spec_rag_scores(rag_query, doc_ids)
        except Exception as e:
            logger.warning(f"사전규격 RAG 점수 조회 실패 (무시): {e}")

    # 3단계: 최종 점수 계산 + upsert
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    matched_count = 0
    new_recommend_count = 0

    for ps, ps_items, matched_items, matched_kws, kw_score, matched_profile_kws, profile_score in candidates:
        item_score = W_ITEM if matched_items else 0.0
        rag_hit = rag_results.get(ps.dify_doc_id) if ps.dify_doc_id else None
        raw_rag = rag_hit["score"] if rag_hit else 0.0
        rag_score = max(0.0, min(1.0, (raw_rag - 0.2) / 0.4))
        score = round(
            item_score + kw_score * W_KEYWORD + profile_score * W_PROFILE + rag_score * W_RFP_RAG, 4
        )

        reasons = []
        if matched_items:
            reasons.append(f"품목코드({', '.join(matched_items[:3])})")
        if matched_kws:
            reasons.append(f"키워드({', '.join(matched_kws[:5])})")
        if matched_profile_kws:
            reasons.append(f"프로필({', '.join(matched_profile_kws[:3])})")
        if rag_score > 0:
            reasons.append(f"RAG({rag_score:.2f})")
        reason = " + ".join(reasons)

        matched_item_names = [items[code] for code in matched_items if code in items]

        kw_json: dict = {
            "items":            matched_items,
            "item_names":       matched_item_names,
            "keywords":         matched_item_names + matched_kws,
            "profile_keywords": matched_profile_kws,
        }
        if rag_hit and rag_hit["score"] > 0:
            kw_json["rag"] = {"score": round(raw_rag, 4), "segment": rag_hit["segment"]}

        existing = db.query(PreSpecCompanyMapping).filter_by(
            company_id=company_id,
            bf_spec_rgst_no=ps.bf_spec_rgst_no,
        ).first()

        if score < 0.40:
            if existing:
                db.delete(existing)
            continue

        if not existing:
            if prespec_limit is not None and today_usage + new_recommend_count >= prespec_limit:
                logger.info(f"기업 {company_id}: PRESPEC_RECOMMEND 일 한도 도달 ({prespec_limit}건), 이후 신규 추천 중단")
                continue
            new_recommend_count += 1

        if existing:
            existing.match_score = score
            existing.match_detail = reason[:1000]
            existing.match_reason = None
            existing.match_keywords = kw_json
            existing.reason_status = "PENDING"
            existing.last_match_dt = now_kst
            flag_modified(existing, "match_keywords")
        else:
            db.add(PreSpecCompanyMapping(
                company_id=company_id,
                bf_spec_rgst_no=ps.bf_spec_rgst_no,
                match_type_cd="AI",
                match_score=score,
                match_detail=reason[:1000],
                match_keywords=kw_json,
                reason_status="PENDING",
                last_match_dt=now_kst,
            ))

        matched_count += 1

    increment_usage(company_id, "PRESPEC_RECOMMEND", new_recommend_count, db)
    db.commit()
    logger.info(f"기업 {company_id}: 사전규격 매칭 완료 {matched_count}건 (신규 {new_recommend_count}건)")
    return {"company_id": company_id, "matched": matched_count}