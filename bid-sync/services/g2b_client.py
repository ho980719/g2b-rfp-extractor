import logging
import math
import os
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

SERVICE_KEY = os.getenv("G2B_SERVICE_KEY", "")
BASE_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"

PRE_SPEC_SERVICE_KEY = os.getenv("G2B_PRE_SPEC_SERVICE_KEY", "")
PRE_SPEC_BASE_URL = "http://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService"
# 업무구분별 오퍼레이션명
PRE_SPEC_OPERATIONS = {
    "Servc": "getPublicPrcureThngInfoServc",  # 용역
    "Thng":  "getPublicPrcureThngInfoThng",   # 물품
}

INTERVAL_MINUTES = 10


async def _fetch_page(client: httpx.AsyncClient, start_str: str, end_str: str, page_no: int) -> dict | None:
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": page_no,
        "numOfRows": 100,
        "inqryDiv": 1,
        "type": "json",
        "inqryBgnDt": start_str,
        "inqryEndDt": end_str,
    }
    try:
        response = await client.get(BASE_URL, params=params, timeout=15.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"G2B API 오류: page={page_no} | {e}")
        return None


def _extract_items(raw: dict) -> list:
    try:
        items = raw["response"]["body"]["items"]
        if isinstance(items, dict):
            item = items.get("item", [])
            return [item] if isinstance(item, dict) else (item or [])
        return items if isinstance(items, list) else []
    except Exception:
        return []


def _get_total_count(raw: dict) -> int:
    try:
        return int(raw["response"]["body"]["totalCount"])
    except Exception:
        return 0


def _current_window() -> tuple[str, str]:
    """현재 시각 기준 직전 10분 구간 반환 (KST)"""
    now = datetime.utcnow() + timedelta(hours=9)
    floored = now.replace(
        minute=(now.minute // INTERVAL_MINUTES) * INTERVAL_MINUTES,
        second=0,
        microsecond=0,
    )
    start = floored - timedelta(minutes=INTERVAL_MINUTES)
    return start.strftime("%Y%m%d%H%M"), floored.strftime("%Y%m%d%H%M")


async def fetch_bids() -> list[dict]:
    """G2B API에서 직전 10분 구간 공고 목록 전체 수집"""
    start_str, end_str = _current_window()
    logger.info(f"G2B 수집 시작: {start_str} ~ {end_str}")

    async with httpx.AsyncClient() as client:
        first = await _fetch_page(client, start_str, end_str, page_no=1)
        if not first:
            return []

        all_items = _extract_items(first)
        total = _get_total_count(first)
        logger.info(f"totalCount={total}")

        if total > 100:
            total_pages = math.ceil(total / 100)
            for page_no in range(2, total_pages + 1):
                page = await _fetch_page(client, start_str, end_str, page_no=page_no)
                if not page:
                    logger.warning(f"페이지 {page_no} 응답 없음, 중단")
                    break
                all_items.extend(_extract_items(page))
                logger.info(f"page={page_no} 수집 누적={len(all_items)}건")

    all_items.sort(key=lambda x: x.get("bidNtceDt", ""), reverse=True)
    logger.info(f"G2B 수집 완료: {len(all_items)}건")
    return all_items


async def _fetch_pre_spec_page(
    client: httpx.AsyncClient,
    operation: str,
    start_str: str,
    end_str: str,
    page_no: int,
) -> dict | None:
    # serviceKey는 이중 인코딩 방지를 위해 URL에 직접 포함
    base = f"{PRE_SPEC_BASE_URL}/{operation}?serviceKey={PRE_SPEC_SERVICE_KEY}"
    params = {
        "pageNo": page_no,
        "numOfRows": 100,
        "inqryDiv": 1,
        "type": "json",
        "inqryBgnDt": start_str,
        "inqryEndDt": end_str,
    }
    try:
        response = await client.get(base, params=params, timeout=15.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"G2B 사전규격 API 오류: op={operation} page={page_no} | {e}")
        return None


def _parse_spec_doc_urls(item: dict) -> list[str]:
    """specDocFileUrl1~5 중 비어있지 않은 URL만 추출해 리스트로 반환"""
    urls = []
    for i in range(1, 6):
        url = (item.get(f"specDocFileUrl{i}") or "").strip()
        if url:
            urls.append(url)
    return urls


async def fetch_pre_specs(bsns_div_list: list[str] | None = None) -> list[dict]:
    """
    G2B 사전규격 API에서 직전 10분 구간 목록 수집.
    bsns_div_list: ["Servc", "Thng"] 등 — None이면 기본값 ["Servc"] 사용
    각 항목에 _parsed_spec_urls 필드 추가 (파싱된 URL 목록)
    """
    if bsns_div_list is None:
        bsns_div_list = ["Servc"]

    start_str, end_str = _current_window()
    logger.info(f"G2B 사전규격 수집 시작: {start_str} ~ {end_str} | 대상={bsns_div_list}")

    all_items: list[dict] = []

    async with httpx.AsyncClient() as client:
        for bsns_div in bsns_div_list:
            operation = PRE_SPEC_OPERATIONS.get(bsns_div)
            if not operation:
                logger.warning(f"알 수 없는 업무구분: {bsns_div}, 스킵")
                continue

            first = await _fetch_pre_spec_page(client, operation, start_str, end_str, page_no=1)
            if not first:
                continue

            items = _extract_items(first)
            total = _get_total_count(first)
            logger.info(f"사전규격 {bsns_div}: totalCount={total}")

            if total > 100:
                total_pages = math.ceil(total / 100)
                for page_no in range(2, total_pages + 1):
                    page = await _fetch_pre_spec_page(client, operation, start_str, end_str, page_no)
                    if not page:
                        logger.warning(f"사전규격 {bsns_div} 페이지 {page_no} 응답 없음, 중단")
                        break
                    items.extend(_extract_items(page))

            # 파싱된 URL 목록 미리 추가
            for item in items:
                item["_parsed_spec_urls"] = _parse_spec_doc_urls(item)

            all_items.extend(items)
            logger.info(f"사전규격 {bsns_div}: {len(items)}건 수집")

    all_items.sort(key=lambda x: x.get("rcptDt", ""), reverse=True)
    logger.info(f"G2B 사전규격 수집 완료: {len(all_items)}건")
    return all_items
