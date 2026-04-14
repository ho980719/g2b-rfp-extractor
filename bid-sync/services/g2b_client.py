import logging
import math
import os
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

SERVICE_KEY = os.getenv("G2B_SERVICE_KEY", "")
BASE_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"
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
